"""SMS provider abstraction — swappable backends for receiving OTP via rented numbers.

Providers:
  - mock     : local, deterministic, for testing (no key)
  - fivesim  : 5sim.net — disposable number rental, cheap, many countries (default)
  - twilio   : Twilio — owned numbers, enterprise/KYC'd tier

A provider implements:
  create_number(country?, service?) -> {id, number, country, service, provider}
  get_sms(id, wait?)                -> {from, text, code, received_at} | None
  release_number(id)                -> None   (stop renting, free the number)
  status()                          -> {provider, ready, detail}
"""
from __future__ import annotations
from abc import ABC, abstractmethod


class SMSProvider(ABC):
    name: str = "base"

    @abstractmethod
    def create_number(self, country: str = "any", service: str = "any") -> dict: ...

    @abstractmethod
    def get_sms(self, number_id: str, wait: float = 60.0) -> dict | None: ...

    @abstractmethod
    def release_number(self, number_id: str) -> None: ...

    @abstractmethod
    def status(self) -> dict: ...
