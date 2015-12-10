import schedule
import time
import astral
from gattlib import GATTRequester
import datetime
import pytz
from threading import Thread
import forecastio
from flask import Flask, render_template, redirect, url_for

# Your geopgraphical coordinates
my_latt = 52.0066700
my_long = 4.355560
my_tz = "Europe/Amsterdam"
# Your elevation above sea level, see http://dateandtime.info
my_elevation = 1

# Your magicblue bulb bluetooth MAC
# Get this by starting your Magicblue app and noting the MAC number. Or use HCITOOL
my_magicblue = "fb:6f:13:a3:c1:98"

# API key for forecast.io
forecast_key = "1bfad3ea61bc652c7e34bf56f759bdfd"

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

## Run the webserver in debug mode?
debug = True

## And on what port?
port = 80

# A dict for mapping colors to forecast weather types
## Expected are clear-day, clear-night, rain, snow, sleet, wind, fog, cloudy, partly-cloudy-day, or partly-cloudy-night
weather_mapping = {"clear-day":light_orange,"clear-night":light_orange, "rain":light_blue, "snow":light_blue,
                    "sleet":light_blue, "wind":light_gray, "fog":light_gray, "cloudy":light_gray,
                   "partly_cloudy_day":light_orange, "partly_cloudy_night":light_orange}

## The magic strings needed by the magicblue bulb
mg_prefix = [0x56]
mg_suffix = [0x00, 0xf0, 0xaa, 0x3b, 0x07, 0x00, 0x01]

def get_forecast():
    forecast_datetime = datetime.datetime.now(pytz.timezone(my_tz))
    hours, minutes = forecast_time.split(':')
    forecast_datetime = forecast_datetime + datetime.timedelta(days = 1);
    forecast_datetime = forecast_datetime.replace(hour=int(hours), minute=int(minutes))
    forecast = forecastio.load_forecast(forecast_key, my_latt, my_long, time=forecast_datetime)
    weather_string = forecast.currently().icon
    return weather_string

def magicblue_color(colorstring):
    req = GATTRequester(my_magicblue, False)
    req.connect(True, "random")
    time.sleep(1)
    req.write_by_handle(0x000c, colorstring)
    time.sleep(1)
    req.disconnect()
    time.sleep(1)

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
    weather_string = get_forecast()
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
    magicblue_color(str(bytearray(colorstring)))

app = Flask(__name__)
@app.route('/')
def queued_jobs():
        jobs = schedule.jobs
        start_time = None
        stop_time = None

        for job in jobs:
                func_name = job.job_func.func.__name__
                if(func_name == "start_magicblue"):
                        start_time = job.next_run
                if(func_name == "stop_magicblue"):
                        stop_time = job.next_run

        sundown = start_time - datetime.timedelta(minutes = minutes_before_sundown)
        forecast = get_forecast()
        return render_template('index.html', start_time=start_time, stop_time = stop_time, sundown = sundown, forecast = forecast)

@app.route('/start_now')
def start_now():
    start_magicblue()
    return redirect("/")

@app.route('/stop_now')
def stop_now():
    stop_magicblue()
    return redirect("/")

def throw_webserver():
    while True:
        schedule.run_pending()
        time.sleep(10)

## Plan lights out every day at the set time
lightsout_time_struct = list((time.strptime(lightsout_hour, "%H:%M"))[:7])
lightsout_time_struct.append(pytz.timezone(my_tz))
lightsout_time = datetime.datetime(*lightsout_time_struct)
schedule.every().day.at(lightsout_hour).do(stop_magicblue)

## And plan the job that will figure out when to start the lamp 5 minutes after that
nextplanning = lightsout_time + datetime.timedelta(minutes=1)
schedule.every().day.at(nextplanning.strftime("%H:%M")).do(schedule_magicblue_start)

## Also, look at the current time and situation. If we are in "on" time, force the lamp
## ON time is defined as: "right now we're somewhere between sundown and lights out"
now = datetime.datetime.now(pytz.timezone(my_tz))
lightson_time = get_lightson_time()

if(lightsout_time.time() > now.time() > lightson_time.time()):
    start_magicblue()
else:
    ## If it's not "ON" time then schedule an ON. After the first run, the lightsout scheduler will take over.
    schedule_magicblue_start()

print(schedule.jobs)



thread = Thread(target = throw_webserver)
thread.daemon=True
thread.start()

app.debug = debug
app.run(host='0.0.0.0', port=port)
