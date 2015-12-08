import schedule
import time
import astral
from gattlib import GATTRequester
import datetime
import pytz
import forecastio

# Your geopgraphical coordinates
my_latt = 52.0066700
my_long = 4.355560
my_tz = "Europe/Amsterdam"

# Your magicblue bluetooth MAC
my_magicblue = "fb:6f:13:a3:c1:98"
# Your elevation above sea level, see http://dateandtime.info
my_elevation = 1

# API key for forecast.io
forecast_key = ""

# The amount of time in minutes before or after sundown  at which we should turn on the light. For example, "-60" to
# kick the lamp into life an hour before dusk. No quotes please.
minutes_before_sundown = -60

# The time at which we should turn the light off, in a HH:MM time. For example, 23:30. Given between quotes.
lightsout_hour = "23:00"

# The time which you would want to use for the forecast. The bulb will jump color accordingly to the weather as
# forecast the next day at this time
forecast_time = "09:00"

## Some color arrays
light_blue = [0x00, 0x99, 0xcc]
light_gray = [0xaa, 0xaa, 0xaa]
light_orange = [0xff, 0xcc, 0x00]
night = [0x00, 0x00, 0x00]

# A dict for mapping colors to forecast weather types
## Expected are clear-day, clear-night, rain, snow, sleet, wind, fog, cloudy, partly-cloudy-day, or partly-cloudy-night
weather_mapping = {"clear-day":light_orange,"clear-night":light_orange, "rain":light_blue, "snow":light_blue,
                    "sleet":light_blue, "wind":light_gray, "fog":light_gray, "cloudy":light_gray,
                   "partly_cloudy_day":light_orange, "partly_cloudy_night":light_orange}

## The magic strings needed by the magicblue bulb
mg_prefix = [0x56]
mg_suffix = [0x00, 0xf0, 0xaa, 0x3b, 0x07, 0x00, 0x01]

def magicblue_color(colorstring):
    req = GATTRequester(my_magicblue, False)
    req.connect(True, "random")
    req.write_by_handle(0x000c, colorstring)
    req.disconnect()

def get_lightson_time():
    myLocation = astral.Location(info=("Delft", "NL", my_latt, my_long, my_tz))
    sundown = myLocation.sunset(lightsout_time)
    lightson = sundown + datetime.timedelta(minutes=minutes_before_sundown)
    return lightson

def schedule_magicblue_start():
    lightson_time = get_lightson_time().strftime("%H:%M")
    schedule.every().day.at(lightson_time).do(start_magicblue)

def start_magicblue():
    ## First, let's toss up a weather forecast. The hard part is creating a good time object
    forecast_datetime = datetime.datetime.now(pytz.timezone(my_tz))
    hours, minutes = forecast_time.split(':')
    forecast_datetime = forecast_datetime + datetime.timedelta(days = 1);
    forecast_datetime = forecast_datetime.replace(hour=int(hours), minute=int(minutes))
    print(str(forecast_datetime))
    forecast = forecastio.load_forecast(forecast_key, my_latt, my_long, time=forecast_datetime)
    weather_string = forecast.currently().icon
    print(weather_string)
    colorstring = []
    colorstring.extend(mg_prefix)
    colorstring.extend(weather_mapping[weather_string])
    colorstring.extend(mg_suffix)
    magicblue_color(str(bytearray(colorstring)))
    return schedule.CancelJob


def stop_magicblue():
    colorstring = []
    colorstring.extend(mg_prefix)
    colorstring.extend(night)
    colorstring.extend(mg_suffix)
    magicblue_color(colorstring)

## Plan lights out every day at the set time
lightsout_time_struct = list((time.strptime(lightsout_hour, "%H:%M"))[:7])
lightsout_time_struct.append(pytz.timezone(my_tz))
lightsout_time = datetime.datetime(*lightsout_time_struct)
schedule.every().day.at(lightsout_hour).do(stop_magicblue)

## And plan the job that will figure out when to start the lamp 5 minutes after that
nextplanning = lightsout_time + datetime.timedelta(minutes=1)
schedule.every().day.at(nextplanning.strftime("%H:%M")).do(schedule_magicblue_start)

## Also, look at the current time and situation. If we are in "on" time, force the lamp on
## if we are
now = datetime.datetime.now(pytz.timezone(my_tz))
lightson_time = get_lightson_time()
if(lightsout_time.time() > now.time() > lightson_time.time()):
    start_magicblue()

print(schedule.jobs)

while True:
    schedule.run_pending()
    time.sleep(10)