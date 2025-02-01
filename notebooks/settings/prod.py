from .base import *

MOTOR_RANGE = [-milli, milli]

MOTOR_NAMES = [  
    "MG-LA1:CLX1-I:Set", 
    "MG-LA1:CLY1-I:Set",
    "MG-LA1:CLX2-I:Set", 
    "MG-LA1:CLY2-I:Set",
    "MG-LA2:CLX3-I:Set", 
    "MG-LA2:CLY3-I:Set",
    "MG-LA3:CLX4-I:Set", 
    "MG-LA3:CLY4-I:Set",
    "MG-LA4:CLX5-I:Set", 
    "MG-LA4:CLY5-I:Set",
    "MG-LA5:CLX6-I:Set", 
    "MG-LA5:CLY6-I:Set",     
]

MOTORS = [[motor_name, MOTOR_RANGE] for motor_name in MOTOR_NAMES]

METER_NAMES = [
    "BI-LA1:PK3-fastAvX:Mea", 
    "BI-LA1:PK3-fastAvY:Mea",
    "BI-LA2:PK4-fastAvX:Mea",
    "BI-LA2:PK4-fastAvY:Mea",
    "BI-LA3:PK5-fastAvX:Mea", 
    "BI-LA3:PK5-fastAvY:Mea",
    "BI-LA4:PK6-fastAvX:Mea", 
    "BI-LA4:PK6-fastAvY:Mea",      
]

METERS = METER_NAMES

DIRNAME_DATA = "data/prod"
