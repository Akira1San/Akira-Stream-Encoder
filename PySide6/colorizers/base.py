from abc import ABC, abstractmethod
import numpy as np


class Colorizer(ABC):
    @abstractmethod
    def colorize_frame(self, l_channel: np.ndarray) -> np.ndarray:
        """Take L channel (HxW float32 0-1), return RGB (HxWx3 uint8)"""
        ...

    @abstractmethod
    def colorize_batch(self, l_batch: np.ndarray) -> np.ndarray:
        """Take batch of L channels (BxHxW float32 0-1), return RGB (BxHxWx3 uint8)"""
        ...

    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def supports_batch(self) -> bool:
        ...

    @abstractmethod
    def supported_filters(self) -> dict:
        ...
