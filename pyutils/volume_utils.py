def db_to_percent(value: float, min_db: float = -100.0) -> float:
    """Convierte un valor en decibelios a un porcentaje de 0 a 100."""
    if value <= min_db:
        return 0.0
    return (1.0 + (value / abs(min_db))) * 100.0

def percent_to_db(percent: float, min_db: float = -100.0) -> float:
    """Convierte un porcentaje de 0 a 100 a su valor equivalente en decibelios."""
    if percent <= 0.0:
        return min_db  # O puedes retornar un valor muy bajo para silencio
    return min_db * (1.0 - (percent / 100.0))