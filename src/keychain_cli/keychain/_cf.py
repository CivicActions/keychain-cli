"""CoreFoundation bindings: just enough to build a query dictionary and read a result.

Every object created here is released by the ``CFObjects`` context manager that created
it. Objects returned by the Security framework are owned by the caller and released with
``release`` after their contents have been copied into Python values.

Reference: ``specs/001-keychain-secret-manager/research/keychain-probe.py``.
"""

from __future__ import annotations

import ctypes
from collections.abc import Iterable, Sequence
from types import TracebackType
from typing import Self

_CF_PATH = "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
CF = ctypes.CDLL(_CF_PATH)

CFTypeRef = ctypes.c_void_p
CFIndex = ctypes.c_long
_UTF8 = 0x08000100
_SINT32 = 3

CF.CFStringCreateWithCString.restype = CFTypeRef
CF.CFStringCreateWithCString.argtypes = [CFTypeRef, ctypes.c_char_p, ctypes.c_uint32]
CF.CFDataCreate.restype = CFTypeRef
CF.CFDataCreate.argtypes = [CFTypeRef, ctypes.c_char_p, CFIndex]
CF.CFNumberCreate.restype = CFTypeRef
CF.CFNumberCreate.argtypes = [CFTypeRef, CFIndex, ctypes.c_void_p]
CF.CFDictionaryCreate.restype = CFTypeRef
CF.CFDictionaryCreate.argtypes = [
    CFTypeRef,
    ctypes.POINTER(CFTypeRef),
    ctypes.POINTER(CFTypeRef),
    CFIndex,
    ctypes.c_void_p,
    ctypes.c_void_p,
]
CF.CFArrayCreate.restype = CFTypeRef
CF.CFArrayCreate.argtypes = [CFTypeRef, ctypes.POINTER(CFTypeRef), CFIndex, ctypes.c_void_p]
CF.CFRelease.restype = None
CF.CFRelease.argtypes = [CFTypeRef]
CF.CFArrayGetCount.restype = CFIndex
CF.CFArrayGetCount.argtypes = [CFTypeRef]
CF.CFArrayGetValueAtIndex.restype = CFTypeRef
CF.CFArrayGetValueAtIndex.argtypes = [CFTypeRef, CFIndex]
CF.CFDictionaryGetValue.restype = CFTypeRef
CF.CFDictionaryGetValue.argtypes = [CFTypeRef, CFTypeRef]
CF.CFGetTypeID.restype = ctypes.c_ulong
CF.CFGetTypeID.argtypes = [CFTypeRef]
CF.CFStringGetTypeID.restype = ctypes.c_ulong
CF.CFDataGetTypeID.restype = ctypes.c_ulong
CF.CFArrayGetTypeID.restype = ctypes.c_ulong
CF.CFDictionaryGetTypeID.restype = ctypes.c_ulong
CF.CFStringGetLength.restype = CFIndex
CF.CFStringGetLength.argtypes = [CFTypeRef]
CF.CFStringGetCString.restype = ctypes.c_bool
CF.CFStringGetCString.argtypes = [CFTypeRef, ctypes.c_char_p, CFIndex, ctypes.c_uint32]
CF.CFDataGetLength.restype = CFIndex
CF.CFDataGetLength.argtypes = [CFTypeRef]
CF.CFDataGetBytePtr.restype = ctypes.POINTER(ctypes.c_ubyte)
CF.CFDataGetBytePtr.argtypes = [CFTypeRef]

_KEY_CALLBACKS = ctypes.addressof(ctypes.c_char.in_dll(CF, "kCFTypeDictionaryKeyCallBacks"))
_VALUE_CALLBACKS = ctypes.addressof(ctypes.c_char.in_dll(CF, "kCFTypeDictionaryValueCallBacks"))
_ARRAY_CALLBACKS = ctypes.addressof(ctypes.c_char.in_dll(CF, "kCFTypeArrayCallBacks"))


def ptr(ref: int | ctypes.c_void_p | None) -> int:
    """Normalize a ctypes pointer or raw address to an int address."""
    if ref is None:
        return 0
    if isinstance(ref, ctypes.c_void_p):
        return ref.value or 0
    return ref


BOOLEAN_TRUE = ptr(CFTypeRef.in_dll(CF, "kCFBooleanTrue"))


def release(ref: int) -> None:
    """Release an object owned by the caller."""
    if ref:
        CF.CFRelease(ref)


class CFObjects:
    """Create CoreFoundation objects and release all of them on exit.

    ``CFDictionaryCreate`` and ``CFArrayCreate`` retain their members, so releasing the
    members and the container together is correct.
    """

    def __init__(self) -> None:
        self._owned: list[int] = []

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        for ref in reversed(self._owned):
            release(ref)
        self._owned.clear()

    def _own(self, ref: int | None) -> int:
        address = ptr(ref)
        if not address:
            msg = "CoreFoundation returned a null object"
            raise MemoryError(msg)
        self._owned.append(address)
        return address

    def string(self, text: str) -> int:
        return self._own(CF.CFStringCreateWithCString(None, text.encode("utf-8"), _UTF8))

    def data(self, raw: bytes) -> int:
        return self._own(CF.CFDataCreate(None, raw, len(raw)))

    def number32(self, value: int) -> int:
        boxed = ctypes.c_int32(value)
        return self._own(CF.CFNumberCreate(None, _SINT32, ctypes.byref(boxed)))

    def dictionary(self, pairs: Sequence[tuple[int, int]]) -> int:
        count = len(pairs)
        keys = (CFTypeRef * count)(*[k for k, _ in pairs])
        values = (CFTypeRef * count)(*[v for _, v in pairs])
        return self._own(
            CF.CFDictionaryCreate(None, keys, values, count, _KEY_CALLBACKS, _VALUE_CALLBACKS)
        )

    def array(self, items: Iterable[int]) -> int:
        members = list(items)
        buffer = (CFTypeRef * len(members))(*members)
        return self._own(CF.CFArrayCreate(None, buffer, len(members), _ARRAY_CALLBACKS))


def is_array(ref: int) -> bool:
    return bool(CF.CFGetTypeID(ref) == CF.CFArrayGetTypeID())


def is_dictionary(ref: int) -> bool:
    return bool(CF.CFGetTypeID(ref) == CF.CFDictionaryGetTypeID())


def is_data(ref: int) -> bool:
    return bool(CF.CFGetTypeID(ref) == CF.CFDataGetTypeID())


def is_string(ref: int) -> bool:
    return bool(CF.CFGetTypeID(ref) == CF.CFStringGetTypeID())


def array_items(ref: int) -> list[int]:
    """Addresses of an array's members. Not retained; valid while ``ref`` lives."""
    count = CF.CFArrayGetCount(ref)
    return [ptr(CF.CFArrayGetValueAtIndex(ref, index)) for index in range(count)]


def dict_get(ref: int, key: int) -> int:
    """Address of a dictionary value, or 0 when the key is absent. Not retained."""
    return ptr(CF.CFDictionaryGetValue(ref, key))


def to_str(ref: int) -> str:
    """Copy a CFString into a Python str."""
    length = CF.CFStringGetLength(ref)
    buffer = ctypes.create_string_buffer(length * 4 + 1)
    if not CF.CFStringGetCString(ref, buffer, len(buffer), _UTF8):
        msg = "CFString could not be converted to UTF-8"
        raise ValueError(msg)
    return buffer.value.decode("utf-8")


def to_bytes(ref: int) -> bytes:
    """Copy CFData into Python bytes."""
    length = CF.CFDataGetLength(ref)
    if length == 0:
        return b""
    pointer = CF.CFDataGetBytePtr(ref)
    return bytes(pointer[:length])
