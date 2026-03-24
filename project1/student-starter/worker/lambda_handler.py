"""
AdFlow Ad Selection Worker
===========================

This Lambda function processes ad opportunity messages from an SQS queue,
applies a quality-adjusted scoring function to select winning bids,
and posts results onward.

Your Tasks:
    1. implement compute_score()    - the scoring formula
    2. implement select_winner()    - pick the winning bid
    3. implement process_opportunity() - full message processing
    4. implement lambda_handler()   - batch processing with failure handling

Logging and Performance:
    Use the logger for all output (not print). Example:
        logger.info("Processed %s in %.1f ms", opportunity_id, elapsed_ms)

    Measure wall-clock time for performance:
        start = time.perf_counter()
        # ... do work ...
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info("Operation took %.1f ms", elapsed_ms)

    To view your logs after deployment:
        aws logs tail /aws/lambda/adflow-YOURID-worker --follow

    To search logs for specific patterns:
        aws logs filter-log-events \
            --log-group-name /aws/lambda/adflow-YOURID-worker \
            --filter-pattern "Batch complete"

    In the AWS Console:
        CloudWatch > Log groups > /aws/lambda/adflow-YOURID-worker
"""

import json
import os
import time
import logging
from datetime import datetime, timezone
from decimal import Decimal

import boto3


# ---------------------------------------------------------------------------
# Logging - CloudWatch picks up anything written to the logger
# ---------------------------------------------------------------------------
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# AWS clients - created once per cold start, reused across invocations
# ---------------------------------------------------------------------------
sqs = boto3.client("sqs")
dynamodb = boto3.resource("dynamodb")

RESULTS_QUEUE_URL = os.environ.get("RESULTS_QUEUE_URL", "")
DYNAMO_TABLE_NAME = os.environ.get("DYNAMO_TABLE_NAME", "")
table = dynamodb.Table(DYNAMO_TABLE_NAME) if DYNAMO_TABLE_NAME else None

# ---------------------------------------------------------------------------
# Scoring constants - from the assignment specification
# ---------------------------------------------------------------------------

# Relevance multiplier: (content_category, advertiser_category) -> multiplier
# Any combination not listed here receives 1.0
RELEVANCE_MAP = {
    ("sports", "sportswear"): 1.4,
    ("sports", "energy_drink"): 1.3,
    ("finance", "fintech"): 1.5,
    ("finance", "insurance"): 1.3,
    ("entertainment", "streaming"): 1.4,
    ("entertainment", "gaming"): 1.3,
    ("lifestyle", "beauty"): 1.3,
    ("lifestyle", "travel"): 1.2,
}

# Time bonus: (start_hour_inclusive, end_hour_exclusive, bonus)
TIME_WINDOWS = [
    (6, 9, 1.20),     # Morning commute
    (12, 14, 1.15),   # Lunch browsing
    (19, 23, 1.25),   # Evening peak
]

# Device bonus
DEVICE_BONUS = {
    "mobile": 1.1,
    "desktop": 1.0,
}


# ---------------------------------------------------------------------------
# Task 1: Scoring Function
# ---------------------------------------------------------------------------

def compute_score(bid, opportunity):
    """
    Compute the quality-adjusted score for a single bid.

    Formula:
        score = bid_amount * relevance_multiplier * time_bonus * device_bonus

    Args:
        bid (dict): Keys: advertiser_id, bid_amount, category
        opportunity (dict): Keys: content_category, device_type, timestamp

    Returns:
        float: the computed score

    TODO: Implement this function. Handle edge cases:
        - What if bid_amount is missing or zero?
        - What if the category combination is not in RELEVANCE_MAP?
        - What if the timestamp cannot be parsed?
    """
    bid_amount = bid.get('bid_amount')
    if bid_amount is None or bid_amount <= 0:
        return 0.0

    content_cat = opportunity.get('content_category')
    ad_cat = bid.get('category')
    relevance_multiplier = RELEVANCE_MAP.get((content_cat, ad_cat), 1.0)

    time_bonus = 1.0
    timestamp_str = opportunity.get('timestamp')
    if timestamp_str:
        try:
            ts = timestamp_str.replace('Z', '+00:00')
            dt = datetime.fromisoformat(ts).astimezone(timezone.utc)
            for start_h, end_h, bonus in TIME_WINDOWS:
                if start_h <= dt.hour < end_h:
                    time_bonus = bonus
                    break
        except Exception:
            pass

    device_type = opportunity.get('device_type')
    device_bonus = DEVICE_BONUS.get(device_type, 1.0)

    score = float(bid_amount) * relevance_multiplier * time_bonus * device_bonus
    return score


# ---------------------------------------------------------------------------
# Task 2: Winner Selection
# ---------------------------------------------------------------------------

def select_winner(opportunity):
    """
    Evaluate all bids for an opportunity and return the winner.

    Args:
        opportunity (dict): Full opportunity including 'bids' list.

    Returns:
        dict with keys:
            winning_advertiser_id (str)
            winning_bid_amount (float)
            winning_score (float)
            score_margin (float) - winning score minus second-place score
        Returns None if there are no valid bids.

    TODO: Implement this function.
        - Score every bid using compute_score()
        - Find the highest score (the winner) and second-highest score
        - Return the result dict with all four fields
    """
    bids = opportunity.get('bids', [])
    if not bids:
        return None

    scored_bids = []
    for bid in bids:
        score = compute_score(bid, opportunity)
        scored_bids.append((score, bid))

    if not scored_bids:
        return None

    scored_bids.sort(key=lambda x: x[0], reverse=True)
    winning_score, winning_bid = scored_bids[0]

    if winning_score == 0.0:
        return None

    second_highest_score = scored_bids[1][0] if len(scored_bids) > 1 else 0.0
    score_margin = winning_score - second_highest_score

    return {
        "winning_advertiser_id": str(winning_bid.get('advertiser_id', '')),
        "winning_bid_amount": float(winning_bid.get('bid_amount', 0.0)),
        "winning_score": float(winning_score),
        "score_margin": float(score_margin)
    }


# ---------------------------------------------------------------------------
# Task 3: Process a Single Opportunity
# ---------------------------------------------------------------------------

def process_opportunity(opportunity):
    """
    Process one opportunity end-to-end:
        1. Select the winning bid
        2. Construct the result record (see result schema below)
        3. Send the result where it needs to go

    Result record schema:
        opportunity_id (str)       - copied from input
        content_category (str)     - copied from input (needed for Part 5 analysis)
        winning_advertiser_id (str)
        winning_bid_amount (float)
        winning_score (float)
        score_margin (float)
        processed_at (str)         - ISO 8601 timestamp of when you processed it

    The processed_at timestamp is how latency is measured. The difference
    between the opportunity's timestamp and your processed_at is the
    end-to-end processing time for that auction.

    Think about:
        - What gets measured (latency on what path)?
        - What is the right order of operations for efficiency?
        - How do you generate the processed_at timestamp?

    Args:
        opportunity (dict): A single ad opportunity message.

    Returns:
        dict: The result record, or None if no valid bids.

    TODO: Implement this function.
    """
    winner_info = select_winner(opportunity)
    if not winner_info:
        return None

    result = {
        "opportunity_id": opportunity.get("opportunity_id"),
        "content_category": opportunity.get("content_category", "unknown"),
        "winning_advertiser_id": winner_info["winning_advertiser_id"],
        "winning_bid_amount": winner_info["winning_bid_amount"],
        "winning_score": winner_info["winning_score"],
        "score_margin": winner_info["score_margin"],
        "processed_at": datetime.now(timezone.utc).isoformat()
    }

    if RESULTS_QUEUE_URL:
        sqs.send_message(
            QueueUrl=RESULTS_QUEUE_URL,
            MessageBody=json.dumps(result)
        )

    if table:
        dynamo_item = {}
        for key, value in result.items():
            if isinstance(value, float):
                dynamo_item[key] = Decimal(str(value))
            else:
                dynamo_item[key] = value
        table.put_item(Item=dynamo_item)

    return result


# ---------------------------------------------------------------------------
# Task 4: Lambda Entry Point with Batch Processing
# ---------------------------------------------------------------------------

def lambda_handler(event, context):
    """
    Lambda entry point. Receives a batch of SQS messages.

    The event contains a 'Records' list. Each record has a 'body' field
    with the JSON-encoded opportunity message, and a 'messageId' field.

    Requirements:
        - Process every message in the batch
        - If a message fails, do NOT let it crash the entire batch
        - Return partial batch failures so SQS retries only the failed messages
        - Log timing for the entire batch

    Return format for partial batch failures:
        {
            "batchItemFailures": [
                {"itemIdentifier": "message-id-that-failed"},
                ...
            ]
        }

    If you return an empty batchItemFailures list, SQS considers all
    messages successfully processed and deletes them from the queue.

    Args:
        event (dict): SQS event with 'Records' list
        context: Lambda context (has aws_request_id, function_name, etc.)

    Returns:
        dict with batchItemFailures

    TODO: Implement this function.
    """
    start_time = time.perf_counter()
    records = event.get("Records", [])
    total = len(records)
    success_count = 0
    failed_message_ids = []

    for record in records:
        try:
            body = json.loads(record.get("body", "{}"))
            process_opportunity(body)
            success_count += 1
        except Exception as e:
            msg_id = record.get("messageId")
            logger.error("Error processing record %s: %s", msg_id, e)
            if msg_id:
                failed_message_ids.append({"itemIdentifier": msg_id})

    duration_ms = (time.perf_counter() - start_time) * 1000
    logger.info("Batch complete: %d/%d succeeded in %.1f ms", success_count, total, duration_ms)

    return {"batchItemFailures": failed_message_ids}
