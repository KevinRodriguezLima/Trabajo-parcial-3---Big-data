from __future__ import annotations


# murmur2 de Kafka (org.apache.kafka.common.utils.Utils). librdkafka lo replica
# bajo el nombre `murmur2_random`, que es lo que configuramos en el producer:
# su default `consistent_random` usa CRC32 y repartiría las mismas claves de
# otra forma que cualquier cliente Java del equipo.
_SEED = 0x9747B28C
_M = 0x5BD1E995
_R = 24
_MASK = 0xFFFFFFFF


def murmur2(data: bytes) -> int:
    length = len(data)
    h = (_SEED ^ length) & _MASK

    for index in range(0, length - length % 4, 4):
        k = (
            data[index]
            | (data[index + 1] << 8)
            | (data[index + 2] << 16)
            | (data[index + 3] << 24)
        )
        k = (k * _M) & _MASK
        k ^= k >> _R
        k = (k * _M) & _MASK
        h = (h * _M) & _MASK
        h ^= k

    remaining = length % 4
    tail = length - remaining
    if remaining == 3:
        h ^= data[tail + 2] << 16
    if remaining >= 2:
        h ^= data[tail + 1] << 8
    if remaining >= 1:
        h ^= data[tail]
        h = (h * _M) & _MASK

    h ^= h >> 13
    h = (h * _M) & _MASK
    h ^= h >> 15
    return h & _MASK


def partition_for_key(key: str, partitions: int) -> int:
    if partitions < 1:
        raise ValueError(f"El número de particiones debe ser mayor que cero, no {partitions}")
    return (murmur2(key.encode("utf-8")) & 0x7FFFFFFF) % partitions
