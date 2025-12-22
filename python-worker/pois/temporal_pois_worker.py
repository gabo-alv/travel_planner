from datetime import timedelta
from typing import Dict, Any, List

from temporalio.exceptions import ActivityError
from temporalio.client import Client
from temporalio.worker import Worker

from pois.workflow_poi_self_improving import SelfImprovingDestinationWorkflow
from pois.pois_self_improving_activities import (
    initial_chat_activity,
    critize_user_itinerary_activity,
    travel_advisory_lookup_activity,
    publish_clientli_message_activity,
    propose_poi_query_activity,
    google_places_activity_with_params,
    review_poi_results_activity,
    summarize_pois_activity,
    generate_update_title_activity
)


def get_pois_worker(client: Client, queue: str = "pois-self-improving-v2") -> Worker:
    return Worker(
        client,
        task_queue= queue,
        identity= queue,
        workflows=[ SelfImprovingDestinationWorkflow],
        activities=[
            initial_chat_activity,
            critize_user_itinerary_activity,
            travel_advisory_lookup_activity,
            publish_clientli_message_activity,
            propose_poi_query_activity,
            google_places_activity_with_params,
            review_poi_results_activity,
            summarize_pois_activity,
            generate_update_title_activity
        ],
    ) 