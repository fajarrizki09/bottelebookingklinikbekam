import re
from typing import Tuple

def is_valid_patient_name(name: str) -> Tuple[bool, str]:
    if not name or len(name.strip()) < 2:
        return False, "Nama terlalu pendek. Minimal 2 karakter."
    
    if len(name) > 100:
        return False, "Nama terlalu panjang. Maksimal 100 karakter."
    
    if not any(c.isalpha() for c in name):
        return False, "Nama harus mengandung huruf."
    
    return True, ""

def is_valid_phone(phone: str) -> Tuple[bool, str]:
    if not phone or len(phone.strip()) < 10:
        return False, "Nomor telepon terlalu pendek. Minimal 10 digit."
    
    phone_clean = phone.strip().replace(" ", "").replace("-", "")
    
    if phone_clean.startswith('+62'):
        phone_clean = phone_clean[3:]
    elif phone_clean.startswith('62'):
        phone_clean = phone_clean[2:]
    elif phone_clean.startswith('0'):
        phone_clean = phone_clean[1:]
    else:
        return False, "Nomor telepon harus dimulai dengan 08, 62, atau +62."
    
    if not phone_clean.isdigit():
        return False, "Nomor telepon hanya boleh mengandung angka."
    
    if len(phone_clean) < 9 or len(phone_clean) > 13:
        return False, "Nomor telepon harus 10-15 digit."
    
    return True, ""

def is_valid_address(address: str) -> Tuple[bool, str]:
    if not address or len(address.strip()) < 5:
        return False, "Alamat terlalu pendek. Minimal 5 karakter."
    
    if len(address) > 500:
        return False, "Alamat terlalu panjang. Maksimal 500 karakter."
    
    return True, ""

def is_valid_therapist_name(name: str) -> Tuple[bool, str]:
    if not name or len(name.strip()) < 2:
        return False, "Nama terlalu pendek. Minimal 2 karakter."
    
    if len(name) > 100:
        return False, "Nama terlalu panjang. Maksimal 100 karakter."
    
    if not any(c.isalpha() for c in name):
        return False, "Nama harus mengandung huruf."
    
    return True, ""
