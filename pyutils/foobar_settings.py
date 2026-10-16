from PyQt6.QtCore import QSettings


SETTINGS_ORGANIZATION = "EtudeTools"
SETTINGS_APPLICATION = "NumHand"
FOOBAR_INTERVENTIONS_KEY = "foobar/interventions_enabled"


def get_foobar_interventions_enabled() -> bool:
    """Return whether file/folder mutations may coordinate with foobar2000.

    The preference defaults to True for compatibility with previous behavior.
    """
    settings = QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)
    return settings.value(FOOBAR_INTERVENTIONS_KEY, True, type=bool)


def set_foobar_interventions_enabled(enabled: bool) -> None:
    """Persist whether mutation workflows may coordinate with foobar2000."""
    settings = QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)
    settings.setValue(FOOBAR_INTERVENTIONS_KEY, bool(enabled))
    settings.sync()
