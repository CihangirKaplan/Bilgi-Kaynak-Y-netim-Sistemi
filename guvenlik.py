import bcrypt

def parola_hashle(parola: str) -> str:
    parola_bytes = parola.encode("utf-8")
    hash_bytes = bcrypt.hashpw(parola_bytes, bcrypt.gensalt())
    return hash_bytes.decode("utf-8")

def parola_dogrula(parola: str, parola_hash: str) -> bool:
    return bcrypt.checkpw(
        parola.encode("utf-8"),
        parola_hash.encode("utf-8")
    )

