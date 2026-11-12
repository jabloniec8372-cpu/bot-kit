"""Transport-agnostic customer conversation: text in, reply texts out.

A Telegram (or Discord, web, ...) adapter only has to call Intake.handle(...)
and send the returned strings. Everything stateful lives in SQLite.
"""
import time

from . import confirm
from .dispatch import submit_once
from .feed import ITEM
from .policy import Policy
from .requests import create_request

DENIED = {
    "BLOCKED": "Requests are paused for your account. Please contact an admin.",
    "PENDING_LIMIT": "You have too many open requests. Please wait for some to finish.",
    "RATE_LIMIT": "You reached the daily request limit. Please try again later.",
}


class Intake:
    def __init__(self, conn, transport, policy=Policy(), ttl=900, clock=lambda: int(time.time())):
        self.conn, self.transport, self.policy, self.ttl, self.clock = conn, transport, policy, ttl, clock

    def handle(self, chat_id, user_id, msg_id, text):
        m = ITEM.search(text)
        if m and len(set(ITEM.findall(text))) == 1:
            confirm.open_confirmation(self.conn, chat_id, user_id, m.group(1), self.ttl, self.clock)
            return [f"Is this the item you want: {m.group(1)}? Send YES or NO."]
        verdict, item = confirm.answer(self.conn, chat_id, user_id, text, self.clock)
        if verdict == "DECLINED":
            return ["Cancelled. Nothing was requested."]
        if verdict == "EXPIRED":
            return ["That confirmation expired. Please send the item again."]
        if verdict != "CONFIRMED":
            return []
        res = create_request(self.conn, chat_id, user_id, msg_id, item, self.policy, self.clock)
        if res.kind == "REPLAY":
            return []
        if res.kind == "DENIED":
            return [DENIED[res.reason]]
        if res.kind == "PREVENTED":
            return [f"{item} is already available, so no request was needed."]
        if res.kind == "DUPLICATE_PENDING":
            return [f"{item} already has a pending request."]
        state, _ = submit_once(self.conn, res.request_id, self.transport, {"item": item}, self.clock)
        return [{
            "CONFIRMED_SUBMITTED": f"Request submitted: {item}. I'll update you when its status changes.",
            "OUTCOME_UNKNOWN": f"{item} is recorded, but the submission result is uncertain. An admin will check.",
            "NOT_SENT": f"{item} is recorded, but the service could not be reached. An admin will check.",
        }.get(state, f"{item} is recorded.")]
