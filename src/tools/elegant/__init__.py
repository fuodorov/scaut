from . import utils, exceptions


def _parse_name(name):
    parts = name.split('.', maxsplit=1)
    if len(parts) == 1:
        return parts[0], None
    return parts[0], parts[1]



def eleget(name, as_string=False):
    try:
        element, field = _parse_name(name)
    except exceptions.ElegantParseError as e:
        utils.elegant_logger.error(e)
        raise e
        
    if element is None or field is None:
        return None
    
    try:
        element_type = utils.get_element_type(element)
        out = utils.get_element_field_value(element, field)
    except (exceptions.ElegantFileNotFoundError, exceptions.ElegantFieldNotFoundError, exceptions.ElegantElementNotFoundError) as e:
        utils.elegant_logger.error(e)
        raise e

    return str(out) if as_string else out


def eleput(name, value):
    if eleget(name) == value:
        utils.elegant_logger.info("Value is not change. Continue!")
        return 1
        
    try:
        element, field = _parse_name(name)
    except exceptions.ElegantParseError as e:
        raise e
        
    if element is None or field is None:
        return -1
    
    try:
        utils.update_parameter(element, field, value)
    except (exceptions.ElegantFileNotFoundError, exceptions.ElegantFieldNotFoundError, exceptions.ElegantElementNotFoundError) as e:
        utils.elegant_logger.error(e)
        raise e
    
    try:
        utils._run_elegant_process()
        return 1
    except exceptions.ElegantProcessError as e:
        utils.elegant_logger.error(e)
        raise e

    