import pandas as pd
from io import StringIO
import csv
import os
import glob 
import uuid
import logging
import subprocess

from ..core import config as cfg
from .exceptions import ElegantFileNotFoundError, ElegantRemoveFileError, ElegantProcessError, ElegantFieldNotFoundError, ElegantElementNotFoundError

elegant_logger = logging.getLogger('Elegant')


def check_file_exists(file):
    if not os.path.isfile(file):
        msg = f"File '{file}' is not exists!"
        elegant_logger.error(msg)
        raise ElegantFileNotFoundError(msg)
    

def _reset_elegant_simulation_data(dir=cfg.ELEGANT_SIMULATION_DATA_DIR):
    elegant_logger.info(f"Resetting Elegant environment data by removing files in directory: {dir}")
    
    for f in glob.glob(f'{dir}/*'): 
        try:
            reset_file_data(f)
        except Exception as e:
            msg = f"Cannot remove file '{f}': {e}"
            elegant_logger.error(msg)
            raise ElegantRemoveFileError(msg)

    elegant_logger.info("Reset of Elegant environment completed.")
    

def reset_file_data(file):
    elegant_logger.info(f"Resetting file data: {file}")
    
    try:
        open(file, 'w').close()
    except Exception as e:
        msg = f"Cannot reset file '{f}': {e}"
        elegant_logger.error(msg)
        raise e

    elegant_logger.info("Reset file completed.")


def _run_elegant_process(file=cfg.ELEGANT_SIMULATION_CONFIG_FILE, dir=cfg.ELEGANT_SIMULATION_DIR):
    check_file_exists(file)
    
    elegant_logger.info(f"Running Elegant with config file '{file}' in directory '{dir}'.")
    _reset_elegant_simulation_data()
    cmd = f'cd {dir} && elegant {file}'
    process = subprocess.run(
        cmd,
        shell=True,
        text=True,
        capture_output=True
    )
    output = process.stdout.splitlines() + process.stderr.splitlines()
    
    if process.returncode != 0:
        msg = f"Elegant run failed with return code {process.returncode} for file: '{file}'"
        elegant_logger.error(msg)
        elegant_logger.debug(output)
        raise ElegantProcessError(msg)
        
    elegant_logger.info("Elegant run completed.")
    elegant_logger.debug(output)


def sdds_to_df(file, columns):
    check_file_exists(file)
    
    elegant_logger.info(f"Converting SDDS file '{file}' to DataFrame with columns={columns}.")
    col_str = "-col=" + ",".join(columns)
    cmd = f'sdds2stream {file} {col_str} -pipe=out'
    process = subprocess.run(
        cmd,
        shell=True,
        text=True,
        capture_output=True
    )
    out = process.stdout.splitlines()

    df = pd.read_table(
        StringIO("\n".join(out)),
        names=columns,
        sep="\\s+",
        engine="python"
    )
    elegant_logger.info("Conversion completed.")
    return df


def _get_element_field_value_from_file(name, parameter, file=cfg.ELEGANT_PARAMETERS_DATA_FILE, occurence=1):
    check_file_exists(file)
    
    elegant_logger.info(
        f"Fetching parameter '{parameter}' from element '{name}' in file '{file}', occurence={occurence}."
    )
    
    if parameter in cfg.ELEGANT_ELEMENT_EXIST_PARAMETERS:
        cmd = (
            f"sddsprocess {file} -pipe=out "
            f"-match=col,ElementName={name.upper()} "
            f"| sdds2stream -pipe -col={parameter}"
        )
        
    else:
        cmd = (
            f"sddsprocess {file} -pipe=out "
            f"-match=col,ElementName={name.upper()} "
            f"-match=col,ElementParameter={parameter.upper()} "
            f"-filter=col,ElementOccurence,{occurence},{occurence} "
            f"| sdds2stream -pipe -col=ParameterValue"
        )
    
    process = subprocess.run(
        cmd,
        shell=True,
        text=True,
        capture_output=True
    )
    out = process.stdout.splitlines()

    if not out:
        msg = "No parameter value found."
        elegant_logger.warning(msg)
        return None

    try:
        val = float(out[-1])
        elegant_logger.debug(f"Parameter value (float): {val}")
        return val
    except ValueError:
        elegant_logger.debug(f"Parameter value (string): {out[-1]}")
        return out[-1]


def get_element_field_value(name, field):
    for file in cfg.ELEGANT_DATA_EXIST_FILES:
        value = _get_element_field_value_from_file(name, field, file)
        if value is not None:
            return value

    msg = f"Field '{field}' is not exists!"
    elegant_logger.error(msg)
    raise ElegantFieldNotFoundError(msg)


def _get_element_type_from_file(name, file=cfg.ELEGANT_PARAMETERS_DATA_FILE):
    check_file_exists(file)
    
    name = name.upper()
    elegant_logger.info(f"Fetching element type for '{name}' from file '{file}'.")
    
    cmd = (
        f"sddsprocess {file} -pipe=out "
        f"-match=col,ElementName={name} "
        f"-filter=col,ElementOccurence,1,1 "
        f"| sdds2stream -pipe -col=ElementType"
    )
    process = subprocess.run(
        cmd,
        shell=True,
        text=True,
        capture_output=True
    )
    out = process.stdout.splitlines()

    if not out:
        elegant_logger.warning("No element type found.")
        return None

    elegant_logger.debug(f"Element type: {out[0]}")
    return out[0]


def get_element_type(name):
    for file in cfg.ELEGANT_EXIST_FILES_WITH_PARAMETERS:
        value = _get_element_type_from_file(name, file)
        if value is not None:
            return value

    msg = f"Element '{name}' is not exists!"
    elegant_logger.warning(msg)

    elegant_logger.warning(f"Try find element {name} after run elegant!")
    # try with run elegant!
    _run_elegant_process()
    for file in cfg.ELEGANT_EXIST_FILES_WITH_PARAMETERS:
        value = _get_element_type_from_file(name, file)
        if value is not None:
            return value
            
    elegant_logger.error(msg)
    raise ElegantElementNotFoundError(msg)



def update_parameter(
    name, parameter, value, 
    file=cfg.ELEGANT_SIMULATION_CONFIG_PARAMETERS_FILE, 
    columns=cfg.ELEGANT_PARAMETERS_DATA_COLUMNS, 
    occurence=1, clear=False
):
    check_file_exists(file)
    
    elegant_logger.info(
        f"Updating parameter '{parameter}' for element '{name}' with value='{value}', "
        f"in file '{file}'."
    )

    elem_type = get_element_type(name)
    old_value = get_element_field_value(name, parameter)

    if not os.path.isfile(file) or clear:
        elegant_logger.debug(f"Creating new DataFrame.")
        df = pd.DataFrame()
    else:
        df = sdds_to_df(file, columns)

    new_row = pd.DataFrame({
        'ElementName':      [name.upper()],
        'ElementParameter': [parameter.upper()],
        'ParameterValue':   [value],
        'ElementType':      [elem_type.upper()],
        'ElementOccurence': [occurence],
        'ElementGroup':     [None]
    })

    df = pd.concat([df, new_row], ignore_index=True)

    tmp_file = os.path.join(cfg.ELEGANT_SIMULATION_DIR, f"{uuid.uuid4()}.txt")
    elegant_logger.debug(f"Writing temporary data to '{tmp_file}'.")
    df.to_csv(tmp_file, sep=' ', index=False, na_rep='""', quoting=csv.QUOTE_NONE)

    elegant_logger.debug(f"Converting '{tmp_file}' back to SDDS file '{file}'.")
    cmd = (
        f'plaindata2sdds {tmp_file} {file} -noRowCount -skiplines=1 '
        f'-column=ElementName,string '
        f'-column=ElementParameter,string '
        f'-column=ParameterValue,double '
        f'-column=ElementType,string '
        f'-column=ElementOccurence,long '
        f'-column=ElementGroup,string'
    )
    subprocess.run(cmd, shell=True, check=True)

    os.remove(tmp_file)
    elegant_logger.info(f"Parameter '{parameter}' for element '{name}' updated successfully.")
