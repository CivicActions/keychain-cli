"""Security framework bindings: item CRUD, keychain files, and status text.

No function here takes or returns a Python secret; values travel as CFData addresses built
by ``_cf.CFObjects``. Nothing here spawns a process or touches ``argv``.
"""

from __future__ import annotations

import ctypes

from keychain_cli.keychain import _cf

_SEC_PATH = "/System/Library/Frameworks/Security.framework/Security"
SEC = ctypes.CDLL(_SEC_PATH)

OSStatus = ctypes.c_int32
CFTypeRef = _cf.CFTypeRef

SEC.SecItemAdd.restype = OSStatus
SEC.SecItemAdd.argtypes = [CFTypeRef, ctypes.POINTER(CFTypeRef)]
SEC.SecItemCopyMatching.restype = OSStatus
SEC.SecItemCopyMatching.argtypes = [CFTypeRef, ctypes.POINTER(CFTypeRef)]
SEC.SecItemUpdate.restype = OSStatus
SEC.SecItemUpdate.argtypes = [CFTypeRef, CFTypeRef]
SEC.SecItemDelete.restype = OSStatus
SEC.SecItemDelete.argtypes = [CFTypeRef]
SEC.SecKeychainCreate.restype = OSStatus
SEC.SecKeychainCreate.argtypes = [
    ctypes.c_char_p,
    ctypes.c_uint32,
    ctypes.c_void_p,
    ctypes.c_bool,
    CFTypeRef,
    ctypes.POINTER(CFTypeRef),
]
SEC.SecKeychainOpen.restype = OSStatus
SEC.SecKeychainOpen.argtypes = [ctypes.c_char_p, ctypes.POINTER(CFTypeRef)]
SEC.SecKeychainDelete.restype = OSStatus
SEC.SecKeychainDelete.argtypes = [CFTypeRef]
SEC.SecCopyErrorMessageString.restype = CFTypeRef
SEC.SecCopyErrorMessageString.argtypes = [OSStatus, ctypes.c_void_p]

# Status codes the store maps to specific outcomes. Everything else is a StoreError.
ERR_DUPLICATE = -25299
ERR_NOT_FOUND = -25300
ERR_INTERACTION_NOT_ALLOWED = -25308
ERR_AUTH_FAILED = -25293
ERR_USER_CANCELED = -128

# Ownership stamp: FourCharCode 'kccl'. Only items carrying it are visible to the tool.
CREATOR_STAMP = 0x6B63636C
SERVICE_PREFIX = "keychain-cli:"


def _constant(name: str) -> int:
    return _cf.ptr(CFTypeRef.in_dll(SEC, name))


class Keys:
    """Addresses of the ``kSec*`` CFString constants used in queries."""

    CLASS = _constant("kSecClass")
    CLASS_GENERIC_PASSWORD = _constant("kSecClassGenericPassword")
    ATTR_SERVICE = _constant("kSecAttrService")
    ATTR_ACCOUNT = _constant("kSecAttrAccount")
    ATTR_CREATOR = _constant("kSecAttrCreator")
    ATTR_GENERIC = _constant("kSecAttrGeneric")
    ATTR_LABEL = _constant("kSecAttrLabel")
    VALUE_DATA = _constant("kSecValueData")
    RETURN_ATTRIBUTES = _constant("kSecReturnAttributes")
    RETURN_DATA = _constant("kSecReturnData")
    MATCH_LIMIT = _constant("kSecMatchLimit")
    MATCH_LIMIT_ALL = _constant("kSecMatchLimitAll")
    USE_KEYCHAIN = _constant("kSecUseKeychain")
    MATCH_SEARCH_LIST = _constant("kSecMatchSearchList")


def status_message(status: int) -> str:
    """The OS description of a status code. Never contains item data."""
    ref = _cf.ptr(SEC.SecCopyErrorMessageString(status, None))
    if not ref:
        return "unknown Security framework error"
    try:
        return _cf.to_str(ref)
    finally:
        _cf.release(ref)


def item_add(attributes: int) -> int:
    """Add one item. Returns the OS status; ``ERR_DUPLICATE`` if it already exists."""
    return int(SEC.SecItemAdd(attributes, None))


def item_copy_matching(query: int) -> tuple[int, int]:
    """Run a query. Returns ``(status, result_address)``; the caller releases the result."""
    result = CFTypeRef()
    status = int(SEC.SecItemCopyMatching(query, ctypes.byref(result)))
    return status, _cf.ptr(result)


def item_update(query: int, changes: int) -> int:
    """Apply ``changes`` to the item matching ``query``. Returns the OS status."""
    return int(SEC.SecItemUpdate(query, changes))


def item_delete(query: int) -> int:
    """Delete the item(s) matching ``query``. Returns the OS status."""
    return int(SEC.SecItemDelete(query))


def keychain_create(path: str, password: bytes) -> tuple[int, int]:
    """Create a keychain file. Returns ``(status, handle)``. Never prompts."""
    handle = CFTypeRef()
    status = int(
        SEC.SecKeychainCreate(
            path.encode("utf-8"), len(password), password, False, None, ctypes.byref(handle)
        )
    )
    return status, _cf.ptr(handle)


def keychain_open(path: str) -> tuple[int, int]:
    """Open an existing keychain file. Returns ``(status, handle)``."""
    handle = CFTypeRef()
    status = int(SEC.SecKeychainOpen(path.encode("utf-8"), ctypes.byref(handle)))
    return status, _cf.ptr(handle)


def keychain_delete(handle: int) -> int:
    """Delete a keychain file and release the handle."""
    return int(SEC.SecKeychainDelete(handle))
