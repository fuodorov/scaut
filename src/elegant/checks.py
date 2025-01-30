from ..core import config as cfg

import .utils as elegant_logger, get_element_type

from .exceptions import ElegantFileNotFoundError, ElegantRemoveFileError, ElegantProcessError, ElegantFieldNotFoundError, ElegantElementNotFoundError


def check_file_exists(file):
    if not os.path.isfile(file):
        msg = f"File '{file}' is not exists!"
        elegant_logger.error(msg)
        raise ElegantFileNotFoundError(msg)


def check_field_exists(field):
    if not field in cfg.ELEGANT_ELEMENT_EXIST_PARAMETERS:
        msg = f"Field '{field}' is not exists!"
        elegant_logger.error(msg)
        raise ElegantFieldNotFoundError(msg)


def check_parameter_exists(name, parameter):
    pass

    
def check_element_exists(element):
    get_element_type(element)
    