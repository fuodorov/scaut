from .base import *

MOTOR_RANGE = [0, milli]

MOTOR_NAMES = [  
    "MG-LA1.CL1.HKICK",
    "MG-LA1.CL1.VKICK",
    "MG-LA1.CL2.HKICK",
    "MG-LA1.CL2.VKICK",
    "MG-LA2.CL3.HKICK",
    "MG-LA2.CL3.VKICK",
    "MG-LA3.CL4.HKICK",
    "MG-LA3.CL4.VKICK",
    "MG-LA4.CL5.HKICK",
    "MG-LA4.CL5.VKICK",
    "MG-LA5.CL6.HKICK", 
    "MG-LA5.CL6.VKICK",     
]

MOTORS = [[motor_name, MOTOR_RANGE] for motor_name in MOTOR_NAMES]

METER_RANGE = [-0.1, 0.1]

METER_NAMES = [
    "BI-LA1.PK3.Cx", 
    "BI-LA1.PK3.Cy",
    "BI-LA2.PK4.Cx", 
    "BI-LA2.PK4.Cy",
    "BI-LA3.PK5.Cx", 
    "BI-LA3.PK5.Cy",
    "BI-LA4.PK6.Cx",
    "BI-LA4.PK6.Cy",
]

METERS = [[meter_name, METER_RANGE] for meter_name in METER_NAMES]

DIRNAME_DATA = "data/dev"
