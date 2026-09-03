# Out-of-Scope

* Rescheduling and cancellation workflows.

---

# Known Issues & Limitations

* **Domain Capability Rejection:** The agent currently fails to explain missing capabilities gracefully (e.g., if a 
user requests a dentist, but the clinic lacks dental services, the agent states there are no available
time slots instead of explicitly clarifying that the service is unsupported).
* **New Patient Compliance Edge Case:** Minor edge case exists where an existing patient might be booked 
with a provider where `accepts_new_patients = false` (detailed in the *New Patient Handling* section).
* **Continuous Slot Fragmentation:** The system does not currently perform schedule compaction or slot 
optimization. Booking a 30-minute appointment inside an open 180-minute window books the whole 180 minute slot
without optimization. (Intentionally left as it is)

---
# Implementation Decisions 

## Context Propagation

### Motivation

To schedule the appointment properly, we should provide the context of all details (locations, providers etc) to the agent to make a decision.
Naive approach to dump all the context as a plain text would make the agent eventually shrink in the size as the 
number of appointment scheduling details grows. That would lead in two inevitable issues: cost and accuracy.

To operate properly, we have a set of policies we should compy with:
  * A provider can only be booked at a location listed in their location_ids.
  * A provider can only be booked for an appointment type listed in their appointment_type_ids.
  * An appointment type with a required_capability can only be booked at a location whose capabilities include that capability (e.g. MRI/X-Ray/CT need 'imaging').
  * Appointment types with requires_referral = true need a referral on file before booking.
  * A new patient may only book appointment types where new_patients_allowed = true, and only with providers where accepting_new_patients = true.
  * When the caller names a provider who practices at multiple locations, the location must be disambiguated before booking.

Rather than expecting the LLM to evaluate complex matrix joins in natural language, we isolate constraint logic into deterministic, 
backend filter tools and present the LLM with pre-filtered, structured tool outputs.

### Data dumping

In real-world application there will probably be some sort of DB to contain all the clinic data. For this, we'll
pick up a Postgres DB to map all of our data, it has a relational data structure therefore has a good match.

For high read traffic, we'll use a Redis as a cache.

### Appointment type classification

We utilize a low-latency model (e.g., `gpt-4o-mini` or `nano`-tier equivalents) strictly to output structured JSON mapping the user's intent to an `appointment_type_id`.

I've used this solution because it was the easiest one in terms for this exercise, but I would consider the alternative
explained below for the production for sake of latency.

**Pros:** 
* Handles informal, ambiguous language and synonyms well out of the box. 
* Caches prompt prefix tokens across concurrent calls.
**Cons:** 
* Latency: Introduces 1-2s latency per classification pass (extremelly slow for voice agents). 
* Ambiguity: prone to top-k ambiguity when symptoms overlap multiple categories.
* Scalability: Degrades at ~500 types.

#### Alternative: embedding-based similarity search 

For larger taxonomies, we generate embeddings for appointment titles/descriptions and run a cosine similarity query 
against a pgvector index, passing only the top-5 candidates to the LLM (if there is a low confidence).

Pros:
* Latency: 50-100 ms, more than x10 times less comparing to LLM call.
* Cost: at 15 QPS the cost of embedding comparison would be ~40$/month
Cons:
* Accuracy: at launch loses accuracy comparing to the LLM approach, needs tuning.

### Clinic Info Lookup

A scheduling agent should be capable of answering questions about locations, doctors, and appointment types. Since
at any point at time the client could ask about doctors, locations etc., we'll provide a tools that will do 
a separate lookups for these entities to let the LLM fetch only what it needs, when it needs it.

We'll start with direct connection to the DB, since the direct lookups would be probably the low friction comparing
to the other queries we'll have described below. We will add additional indexes so the lookup would be
relatively fast (clinic info probably won't be changed very frequently in comparison to calendar, so we
are safe with indexes):

| Pass       | SQL                                                               | Index used          | Latency |
|------------|-------------------------------------------------------------------|---------------------|---------|
| Exact name | WHERE lower(name) = lower($1)                                     | lower(name) B-tree  | ~1ms    |
| Substring  | WHERE lower(name) LIKE '%' \|\| lower($1) \|\| '%'                | lower(name) B-tree  | ~2ms    |
| Fuzzy      | WHERE similarity(name,$1) > 0.3 ORDER BY similarity DESC LIMIT 1  | gin_trgm_ops        | ~2ms    |             

As an improvement point, if we see an elevated rate of DB lookups, we can have a Redis cache before DB query.

Additionally, we can have DB partitioning based on the region, since clients will most probably fetch the information
in their home country / region.

### Appointment results filtering

Basically I divided the problem into two parts: 
1. The hard filtering: e.g. the doctor should be able to provide the appointment type, clinic should have a MRI
capabilities to provide MRI appointments etc
2. The user preferences filtering: "Could I ask for a morning appointment?" - so we should prioritize the appointments
with mornings time slots available

We don't want to store everything in the agent context, as for high data volume, it either has a great cost, either 
it has a chance to not fit in context window at all. 

We'll use the following parts as a workaround. 

#### Per-session cached hard-filtered data

We'll divide this search into two distint queries - one to find the matched (provider, location, appointment) and 
second to fetch the provider calendar data. That's needed because the clinic info provider, location and appointment
types changes rarely comparing to the calendar availability.

For this, we'll have a setup materialized views in DB for (provider, location, appointment) triples. As a future improvement, we could cache these pairs per appointment type with a 24-hour TTL (useful when many callers book the same common appointment type, e.g. general consultations) — this is out of scope for the current implementation.

It's out-of-scope for this implementation, but in the real-world scenario we would certainly need a CDC 
(e.g. Debezium) that would invalidate the cache and update the materialized views on clinic info change
(in case if doctor resigns today, we don't want to keep scheduling appointments).
Or we can leverage some event-based systems, if we consume the information about clinic changes from external providers.

In case of the calendar data, that's changing pretty quick with high load we'll use a combination of 
caching and optimistic lock on DB. For each caller we'll have a cached hard-filtered data that could be later 
altered with user preferences. 
In case, the user changes its mind (e.g. Dr.Amanda has the available slot next week, so I'd rather go to 
any doctor but ASAP) we could faster fetch the already fetched information from the cache without querying 
DB again.
After the user is happy with a time slot, we confirm it with a single atomic `UPDATE ... WHERE available = TRUE` (optimistic lock). If the slot was taken between selection and confirmation, the update affects 0 rows and the agent immediately offers the next available options — no separate SELECT + UPDATE race condition.

Any preferences the caller expressed earlier in the call (provider, location, time of day) are automatically applied when the slot search begins, with a graceful fallback to unfiltered results if no slots match those preferences. When a filter applied mid-search returns zero results, the session state is not modified — the agent re-offers the previous valid options without requiring another tool call.

##### Diversity sampling

In case we still return a lot of results (e.g. the user doesn't have any preferences), we don't want to present
all these results to a user, but we rather pick a limited number of appointment options. Slots are stored in a Redis sorted set with a composite score:

`score = days_until × 1000 + time_bucket × 100 + provider_rank`

where 
* `provider_rank` orders providers so that those accepting new patients appear first, followed by those who do not. 
* `time_bucket` is 0,1,2 meaning morning, afternoon and evening respectively, meaning morning slots have more priority.
* `days_until` calculates the days until the first free time slot, making the earliest slots come earlier.

Note that this does not guarantee provider or location diversity — if one provider has the three earliest slots, all three may surface before any other provider. The caller can always ask for more options or filter explicitly by provider or location.

### New-comers sorting

A new patient may only book appointment types where new_patients_allowed = true, and only with providers where accepting_new_patients = true.

#### Option 1. Explicitly gather providers
We can ask the client whether it's a recurring visit and ask the client which doctors it has seen before (there could be many, we don't know)       

Pros: 
* No false positives: we will filter all providers the user has seen before
* No additional step required on the end, booking can be proceeded with no problem
Cons:
* User can forget, lie about the providers, there could be many of them, not very user-friendly

#### Option 2. Double check at the very end.

Pros:
* No chances to accidentally book the wrong provider.
Cons:
* High chances of going back, probably would be annoying for the clients if there are few such cases                                     
#### Option 3. Partial filtering. [Preferred]

We can check as a gating question once we see new_patients_allowed=False on the appointment type. 
We can ask whether it's a new visit - reject patient, if a recurring, ask the specialist it visited before, and filter 
the specialist based on that. 
We also provide a ranking for the providers, ranking the accepts_new=True higher, so the agent will propose
them first. Until the user explicilitly tells the specific provider, or there are no slots for another one - the 
agent won't propose slots.

Pros: 
* Early filtering for appointments with new_patients_allowed=False
* Relatively small complexity of change
Cons:
* We still can book the provider that doesn't accept new clients.

#### Option 4. External provider

The perfect solution would be to connect to some EHR to collect the identity data and filter out the providers
the client has seen on our own, but we don't have it in our challenge, so we will choose from previous options.

## Bot Creation Strategy

### Option 1: Real-Time Updates

Automatically update and persist the bot in real time whenever the schema changes.

* **Pros:**
  * **Zero Latency on Connect:** Pressing the "Connect" button provides an immediate response because the latest state is already saved.
* **Cons:**
  * **High Traffic Volume:** Every component addition or schema tweak requires a backend network request to persist state and return validation errors.
  * **Concurrency Risks:** Rapid client edits can cause race conditions where out-of-order requests corrupt database state (unless complex queueing or locking is implemented).

---

### Option 2: Save on "Connect"

Persist and validate the agent schema only when the user clicks the "Connect" button.

* **Pros:**
  * **Low Traffic:** Network activity is reduced to a single payload when the user initiates a connection.
* **Cons:**
  * **Tightly Coupled Operations:** Unlinks error boundaries; if schema creation or saving fails, the connection attempt fails as well.
  * **Unclear UI Feedback:** The user lacks visibility into whether their progress is saved before attempting to connect.

---

### Option 3: Explicit "Save" with Real-Time Validation **(Recommended)**

Validate the schema in real time as the user edits, but require an explicit action ("Save" button) to persist changes to the database.

* **Validation Strategy:**
  * Client-side validation handles immediate structural checks.
  * Stateless, in-memory backend requests handle complex domain validation without writing to the database.
* **Save & Connect Workflow:**
  * The schema persists to the database only when the user clicks **Save**.
  * The **Connect** button remains disabled until the current edits are saved, preventing connections to outdated agent versions.
  * Supports optimistic locking in the database for safe concurrency control
  * We might add an optional "Revert" action for un-saved changes to bring the schema to it's last saved version.
  * If user unwillingly closes the tab - we might use cache so the changes won't be lost.
* **Pros:**
  * **Manageable Database Load:** Writes occur strictly on explicit saves, while validation load is offloaded to lightweight stateless services.
  * **Clear UX Mental Model:** Decoupling saving from connecting gives users explicit control and clear visibility over their draft state.
* **Cons:**
  * **Gated Connection Flow:** Disabling the "Connect" button during unsaved states introduces an extra step for the user.

---

# Improvement Plan

* **Embedding-based appointment classification:** Replace the LLM classifier with a pgvector cosine similarity search for appointment type resolution. Reduces classification latency from ~1-2s to ~50-100ms, which is significant for a voice agent. LLM re-ranking of the top-5 candidates is retained only when confidence is low. See the *Appointment type classification* section for the full trade-off analysis.

* **Redis cache for eligible pairs:** Cache the materialized `(provider, location, appointment_type)` triples per appointment type with a 24-hour TTL. Removes a DB read for popular appointment types when multiple callers book the same type concurrently (e.g. general consultations). Requires a CDC mechanism (e.g. Debezium) to invalidate on catalog changes.

* **Redis cache for clinic info lookups:** Add a Redis read-through cache in front of the name-resolution DB queries (`lookup_provider`, `lookup_location`, `lookup_appointment_type`). Beneficial under elevated lookup rates; clinic data changes infrequently so cache hit rates would be high.

* **GIN trigram index migration:** The current trigram similarity search is effectively O(n) over matching trigrams — acceptable for small catalogs but degrades under high concurrent lookup volume (> 100 QPS) or large entity counts (> 10k providers). The Redis cache above should be the first mitigation. If that is insufficient, migrating the fuzzy pass in `resolve_id` to a pgvector HNSW index (approximate nearest-neighbour on pre-computed embeddings) would handle both scale axes without changing any tool or agent code — the migration surface is a single function.

* **RAG for semantic clinic entity resolution:** The current name-resolution pipeline (exact → substring → trigram) handles typos and partial names well, but fails on semantic queries — e.g. "someone who speaks Mandarin near downtown" or "a dermatologist who also does cosmetic procedures". Replacing or augmenting the fuzzy pass with a pgvector embedding search over provider/location profiles would let the LLM resolve entities from natural descriptions rather than requiring the caller to know a name. Clinic entities change infrequently, so embeddings can be pre-computed and refreshed via CDC on catalog writes. The lookup tools would remain the same from the LLM's perspective; only the resolution backend changes.

* **DB partitioning by region:** Partition `calendar_slots` (and optionally `providers`/`locations`) by region so queries are physically local to the caller's geography. Meaningful once the system operates across multiple regions.

* **EHR integration for new patient identity:** Connect to an EHR (e.g. Epic FHIR, Athena) to resolve the caller's identity and retrieve their visit history. This eliminates the remaining edge case where a new patient is booked with a provider who has `accepting_new = false`, and removes the need to ask the caller whether they are a returning patient.

* **Provider/location diversity in initial options:** The current composite score surfaces the earliest slots regardless of provider or location variety. A post-sort diversity pass — e.g. pick the top slot per provider first, then fill remaining slots by score — would ensure the first options presented span different doctors and clinics. This requires changing `get_options` in `filters/_slot_helpers.py` from a plain `ZRANGE` slice to a diversity-aware selection loop over the sorted set.

* **Slot compaction / schedule optimization:** When a booking covers only part of a larger open window, split the window and return the remaining portion as a new available slot rather than marking the entire window unavailable.

* **Capability-aware rejection messaging:** When no slots are returned because the selected location lacks a required capability (e.g. no imaging equipment for an MRI appointment), surface a clear explanation to the caller rather than a generic "no slots available" message.

* **Rescheduling and cancellation workflows:** Allow callers to modify or cancel existing appointments. Requires a patient identity lookup to retrieve their booking reference.