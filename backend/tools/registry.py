from pipecat_flows import FlowsFunctionSchema

from .filters import (
    clear_filter,
    filter_by_location,
    filter_by_provider,
    filter_by_time,
    get_next_options,
    init_slot_search,
)
from .lookups import lookup_appointment_type, lookup_location, lookup_provider
from .scheduling import (
    book_slot,
    capture_preference,
    check_appointment_requirements,
    classify_appointment,
)

REGISTRY: dict[str, FlowsFunctionSchema] = {
    # Scheduling
    book_slot.name: book_slot,
    classify_appointment.name: classify_appointment,
    check_appointment_requirements.name: check_appointment_requirements,
    capture_preference.name: capture_preference,
    # Filters
    init_slot_search.name: init_slot_search,
    filter_by_location.name: filter_by_location,
    filter_by_provider.name: filter_by_provider,
    filter_by_time.name: filter_by_time,
    get_next_options.name: get_next_options,
    clear_filter.name: clear_filter,
    # Lookups
    lookup_location.name: lookup_location,
    lookup_provider.name: lookup_provider,
    lookup_appointment_type.name: lookup_appointment_type,
}

# Tools injected on every node — available regardless of what the JSON declares.
GLOBAL_TOOLS: frozenset[str] = frozenset({
    "lookup_location",
    "lookup_provider",
    "lookup_appointment_type",
    "capture_preference",
})