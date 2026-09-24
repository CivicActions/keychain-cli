"""Research probe: can Python ctypes drive Security.framework for keychain-cli's needs?

Creates a throwaway keychain file under a temp dir, adds two stamped items, lists them by
creator stamp (attributes only), reads one value back, deletes, and removes the keychain.
Placeholder values only. Never touches the login keychain.
"""
import ctypes
import ctypes.util
import os
import sys
import tempfile

CF = ctypes.CDLL(ctypes.util.find_library("CoreFoundation"))
Sec = ctypes.CDLL(ctypes.util.find_library("Security"))

CFTypeRef = ctypes.c_void_p
CFIndex = ctypes.c_long
OSStatus = ctypes.c_int32
kCFStringEncodingUTF8 = 0x08000100
kCFNumberSInt32Type = 3

CF.CFStringCreateWithCString.restype = CFTypeRef
CF.CFStringCreateWithCString.argtypes = [CFTypeRef, ctypes.c_char_p, ctypes.c_uint32]
CF.CFDataCreate.restype = CFTypeRef
CF.CFDataCreate.argtypes = [CFTypeRef, ctypes.c_char_p, CFIndex]
CF.CFNumberCreate.restype = CFTypeRef
CF.CFNumberCreate.argtypes = [CFTypeRef, CFIndex, ctypes.c_void_p]
CF.CFDictionaryCreate.restype = CFTypeRef
CF.CFDictionaryCreate.argtypes = [CFTypeRef, ctypes.POINTER(CFTypeRef), ctypes.POINTER(CFTypeRef), CFIndex, ctypes.c_void_p, ctypes.c_void_p]
CF.CFArrayCreate.restype = CFTypeRef
CF.CFArrayCreate.argtypes = [CFTypeRef, ctypes.POINTER(CFTypeRef), CFIndex, ctypes.c_void_p]
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
CF.CFNumberGetValue.restype = ctypes.c_bool
CF.CFNumberGetValue.argtypes = [CFTypeRef, CFIndex, ctypes.c_void_p]

kKeyCB = ctypes.addressof(ctypes.c_char.in_dll(CF, "kCFTypeDictionaryKeyCallBacks"))
kValCB = ctypes.addressof(ctypes.c_char.in_dll(CF, "kCFTypeDictionaryValueCallBacks"))
kArrCB = ctypes.addressof(ctypes.c_char.in_dll(CF, "kCFTypeArrayCallBacks"))
kCFBooleanTrue = CFTypeRef.in_dll(CF, "kCFBooleanTrue")

Sec.SecItemAdd.restype = OSStatus
Sec.SecItemAdd.argtypes = [CFTypeRef, ctypes.POINTER(CFTypeRef)]
Sec.SecItemCopyMatching.restype = OSStatus
Sec.SecItemCopyMatching.argtypes = [CFTypeRef, ctypes.POINTER(CFTypeRef)]
Sec.SecItemDelete.restype = OSStatus
Sec.SecItemDelete.argtypes = [CFTypeRef]
Sec.SecItemUpdate.restype = OSStatus
Sec.SecItemUpdate.argtypes = [CFTypeRef, CFTypeRef]
Sec.SecKeychainCreate.restype = OSStatus
Sec.SecKeychainCreate.argtypes = [ctypes.c_char_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_bool, CFTypeRef, ctypes.POINTER(CFTypeRef)]
Sec.SecKeychainDelete.restype = OSStatus
Sec.SecKeychainDelete.argtypes = [CFTypeRef]
Sec.SecCopyErrorMessageString.restype = CFTypeRef
Sec.SecCopyErrorMessageString.argtypes = [OSStatus, ctypes.c_void_p]

def K(name):
    return CFTypeRef.in_dll(Sec, name)

def cfstr(s):
    return CF.CFStringCreateWithCString(None, s.encode(), kCFStringEncodingUTF8)

def cfdata(b):
    return CF.CFDataCreate(None, b, len(b))

def cfnum32(n):
    v = ctypes.c_int32(n)
    return CF.CFNumberCreate(None, kCFNumberSInt32Type, ctypes.byref(v))

def cfdict(pairs):
    n = len(pairs)
    keys = (CFTypeRef * n)(*[k for k, _ in pairs])
    vals = (CFTypeRef * n)(*[v for _, v in pairs])
    return CF.CFDictionaryCreate(None, keys, vals, n, kKeyCB, kValCB)

def cfarray(items):
    arr = (CFTypeRef * len(items))(*items)
    return CF.CFArrayCreate(None, arr, len(items), kArrCB)

def pystr(ref):
    n = CF.CFStringGetLength(ref)
    buf = ctypes.create_string_buffer(n * 4 + 1)
    assert CF.CFStringGetCString(ref, buf, len(buf), kCFStringEncodingUTF8)
    return buf.value.decode()

def pybytes(ref):
    n = CF.CFDataGetLength(ref)
    p = CF.CFDataGetBytePtr(ref)
    return bytes(p[:n])

def errmsg(status):
    ref = Sec.SecCopyErrorMessageString(status, None)
    s = pystr(ref) if ref else "?"
    if ref:
        CF.CFRelease(ref)
    return f"{status} ({s})"

def check(status, what):
    if status != 0:
        raise SystemExit(f"FAIL {what}: {errmsg(status)}")
    print(f"ok   {what}")

STAMP = int.from_bytes(b"kccl", "big")  # FourCharCode creator stamp

tmpdir = tempfile.mkdtemp(prefix="kc-probe-")
kc_path = os.path.join(tmpdir, "probe.keychain-db")
kc = CFTypeRef()
pw = b"probe-not-a-secret"
check(Sec.SecKeychainCreate(kc_path.encode(), len(pw), pw, False, None, ctypes.byref(kc)), "SecKeychainCreate temp keychain")
try:
    def add(ns_key, ns_display, var, value):
        attrs = cfdict([
            (K("kSecClass"), K("kSecClassGenericPassword")),
            (K("kSecAttrService"), cfstr(f"keychain-cli:{ns_key}")),
            (K("kSecAttrAccount"), cfstr(var)),
            (K("kSecAttrCreator"), cfnum32(STAMP)),
            (K("kSecAttrLabel"), cfstr(f"keychain-cli: {ns_display}/{var}")),
            (K("kSecAttrGeneric"), cfdata(ns_display.encode())),
            (K("kSecValueData"), cfdata(value.encode())),
            (K("kSecUseKeychain"), kc),
        ])
        return Sec.SecItemAdd(attrs, None)

    check(add("client-a", "Client-A", "API_TOKEN", "placeholder-1"), "SecItemAdd item 1")
    check(add("client-a", "Client-A", "DB_PASSWORD", "placeholder-2"), "SecItemAdd item 2")
    check(add("other", "other", "X", "placeholder-3"), "SecItemAdd item 3 (other ns)")
    dup = add("client-a", "Client-A", "API_TOKEN", "placeholder-dup")
    print(f"ok   duplicate add -> {errmsg(dup)}  (expect -25299 errSecDuplicateItem)")
    assert dup == -25299

    # Enumerate by creator stamp, attributes only, all matches, scoped to temp keychain.
    q = cfdict([
        (K("kSecClass"), K("kSecClassGenericPassword")),
        (K("kSecAttrCreator"), cfnum32(STAMP)),
        (K("kSecMatchSearchList"), cfarray([kc])),
        (K("kSecMatchLimit"), K("kSecMatchLimitAll")),
        (K("kSecReturnAttributes"), kCFBooleanTrue),
    ])
    out = CFTypeRef()
    check(Sec.SecItemCopyMatching(q, ctypes.byref(out)), "SecItemCopyMatching by creator stamp (attrs only)")
    assert CF.CFGetTypeID(out) == CF.CFArrayGetTypeID()
    rows = []
    for i in range(CF.CFArrayGetCount(out)):
        d = CF.CFArrayGetValueAtIndex(out, i)
        svc = pystr(CF.CFDictionaryGetValue(d, K("kSecAttrService")))
        acct = pystr(CF.CFDictionaryGetValue(d, K("kSecAttrAccount")))
        gen = pybytes(CF.CFDictionaryGetValue(d, K("kSecAttrGeneric"))).decode()
        has_data = CF.CFDictionaryGetValue(d, K("kSecValueData")) is not None
        rows.append((svc, acct, gen, has_data))
    CF.CFRelease(out)
    for r in sorted(rows):
        print("     ", r)
    assert len(rows) == 3 and not any(r[3] for r in rows), "attrs-only must not return data"

    # Read one value back (data only) by exact service+account.
    q2 = cfdict([
        (K("kSecClass"), K("kSecClassGenericPassword")),
        (K("kSecAttrService"), cfstr("keychain-cli:client-a")),
        (K("kSecAttrAccount"), cfstr("DB_PASSWORD")),
        (K("kSecMatchSearchList"), cfarray([kc])),
        (K("kSecReturnData"), kCFBooleanTrue),
    ])
    out2 = CFTypeRef()
    check(Sec.SecItemCopyMatching(q2, ctypes.byref(out2)), "SecItemCopyMatching read data")
    assert pybytes(out2) == b"placeholder-2"
    CF.CFRelease(out2)
    print("ok   value round-trip")

    # Update (forced overwrite path).
    upd_q = cfdict([
        (K("kSecClass"), K("kSecClassGenericPassword")),
        (K("kSecAttrService"), cfstr("keychain-cli:client-a")),
        (K("kSecAttrAccount"), cfstr("API_TOKEN")),
        (K("kSecMatchSearchList"), cfarray([kc])),
    ])
    check(Sec.SecItemUpdate(upd_q, cfdict([(K("kSecValueData"), cfdata(b"placeholder-new"))])), "SecItemUpdate")

    # Non-ASCII / newline value round trip.
    check(add("client-a", "Client-A", "MULTI", "line1\nline2 ünïcödé 🔑"), "SecItemAdd multi-line unicode")
    q3 = cfdict([
        (K("kSecClass"), K("kSecClassGenericPassword")),
        (K("kSecAttrService"), cfstr("keychain-cli:client-a")),
        (K("kSecAttrAccount"), cfstr("MULTI")),
        (K("kSecMatchSearchList"), cfarray([kc])),
        (K("kSecReturnData"), kCFBooleanTrue),
    ])
    out3 = CFTypeRef()
    check(Sec.SecItemCopyMatching(q3, ctypes.byref(out3)), "read multi-line unicode")
    assert pybytes(out3).decode() == "line1\nline2 ünïcödé 🔑"
    CF.CFRelease(out3)

    # Delete whole namespace: creator + service.
    del_q = cfdict([
        (K("kSecClass"), K("kSecClassGenericPassword")),
        (K("kSecAttrCreator"), cfnum32(STAMP)),
        (K("kSecAttrService"), cfstr("keychain-cli:client-a")),
        (K("kSecMatchSearchList"), cfarray([kc])),
        (K("kSecMatchLimit"), K("kSecMatchLimitAll")),
    ])
    check(Sec.SecItemDelete(del_q), "SecItemDelete namespace (all matching)")
    out4 = CFTypeRef()
    st = Sec.SecItemCopyMatching(q, ctypes.byref(out4))
    remaining = CF.CFArrayGetCount(out4) if st == 0 else 0
    print(f"     remaining after ns delete: {remaining} (expect 1)")
    assert remaining == 1
    nf = Sec.SecItemCopyMatching(q2, ctypes.byref(CFTypeRef()))
    print(f"ok   missing item -> {errmsg(nf)}  (expect -25300 errSecItemNotFound)")
    assert nf == -25300
finally:
    st = Sec.SecKeychainDelete(kc)
    print(f"cleanup SecKeychainDelete -> {st}; file exists: {os.path.exists(kc_path)}")
    for f in os.listdir(tmpdir):
        os.remove(os.path.join(tmpdir, f))
    os.rmdir(tmpdir)
print("PROBE PASSED")
