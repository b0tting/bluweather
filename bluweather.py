#!/usr/bin/python

import schedule
import time
import astral
import datetime
import pytz
from threading import Thread
import os
import forecastio
from flask import Flask, render_template, redirect, url_for
import logging
from subprocess import PIPE, Popen, call, STDOUT

# Your geopgraphical coordinates
my_latt = 52.0066700
my_long = 4.355560
## Don't make the europe/amsterdam mistake!
my_tz = "CET"
# Your elevation above sea level, see http://dateandtime.info
my_elevation = 1

# Your magicblue bulb bluetooth MAC
# Get this by starting your Magicblue app and noting the MAC number. Or use HCITOOL
my_magicblue = "fb:6f:13:a3:c1:98"

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
light_blue = "0099cc"
light_gray = "aaaaaa"
light_orange = "ffcc00"
night = "000000"

code_off = "cc2433"
code_on = "cc2333"
## Run the webserver in debug mode?
debug = False

## And on what port?
port = 80

gatttool_location="/usr/bin/gatttool"

## Logging default level. Set to logging.INFO for more detailed info
logging.basicConfig(level=logging.ERROR)

logger = logging.getLogger("bluweather")


## Pretty screen dates format string
pretty_date_string = "%A %H:%M"

# A dict for mapping colors to forecast weather types
## Expected are clear-day, clear-night, rain, snow, sleet, wind, fog, cloudy, partly-cloudy-day, or partly-cloudy-night
weather_mapping = {"clear-day":light_orange,"clear-night":light_orange, "rain":light_blue, "snow":light_blue,
                    "sleet":light_blue, "wind":light_gray, "fog":light_gray, "cloudy":light_gray,
                   "partly-cloudy-day":light_orange, "partly-cloudy-night":light_orange}

## The magic strings needed by the magicblue bulb
mg_prefix = "56"
mg_suffix = "00f0aa3b070001"


def get_forecast():
    ## Note that the forecastio library will be queried with a specific timezone!
    forecast_datetime = datetime.datetime.now(my_pytz)
    hours, minutes = forecast_time.split(':')
    forecast_datetime = forecast_datetime + datetime.timedelta(days = 1);
    forecast_datetime = forecast_datetime.replace(hour=int(hours), minute=int(minutes))
    forecast = forecastio.load_forecast(forecast_key, my_latt, my_long, time=forecast_datetime)
    weather_string = forecast.currently().icon
    return weather_string


def gatttool_call(value):
    ## Logger abuse!! If we are at a higher error level then just ERROR, use Popen instead of call().
    ## This will lag the updates, but will actually display errors
    if(logger.level < logging.ERROR):
        p = Popen([gatttool_location, "-t", "random", "-b", my_magicblue, "--char-write", "--handle=0x000c", "--value="+value], stdout=PIPE, stderr=PIPE)
        stdout, stderr = p.communicate()
        ## The actual error when not finding the BT addres is "connect error: Transport endpoint is not connected (107)"
        if(stderr.find("107") > -1):
            logger.error("Could not connect to Magicblue lamp " + my_magicblue + ". Is the power on?")
    else:
        call([gatttool_location, "-t", "random", "-b", my_magicblue, "--char-write", "--handle=0x000c", "--value="+value], stderr=STDOUT)
    time.sleep(0.4)

def magicblue_send(colorstring):
    gatttool_call(code_on)
    time.sleep(0.5)
    gatttool_call(colorstring)
    time.sleep(0.5)

def magicblue_off():
    # Set an 'off' color first, so next time the lamp starts it will not jump colors,
    # which is ugly.
    gatttool_call(mg_prefix + night + mg_suffix)
    time.sleep(0.5)
    gatttool_call(code_off)
    time.sleep(1)


def get_lightson_utctime():
    myLocation = astral.Location(info=("Delft", "NL", my_latt, my_long, my_tz))
    sundown = myLocation.sunset(lightsout_time)
    lightson = sundown + datetime.timedelta(minutes=minutes_before_sundown)
    return lightson.astimezone(pytz.utc)

def schedule_magicblue_start():
    lightson_time = get_lightson_utctime().strftime("%H:%M")
    schedule.every().day.at(lightson_time).do(start_magicblue)

def start_magicblue():
    ## First, let's toss up a weather forecast. The hard part is creating a good time object
    weather_string = get_forecast()
    colorstring = mg_prefix + weather_mapping[weather_string] + mg_suffix
    magicblue_send(colorstring)
    return schedule.CancelJob

def stop_magicblue():
    magicblue_off()

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
	
	if start_time is None:
		## This will only happen once: if we started while the lamp should already be on
		sundown_pretty = False	
		my_pretty_start = False
	else: 
	        sundown = start_time - datetime.timedelta(minutes = minutes_before_sundown)
	        sundown_pretty = pytz.utc.localize(sundown).astimezone(my_pytz).strftime(pretty_date_string)
        	my_pretty_start = pytz.utc.localize(start_time).astimezone(my_pytz).strftime(pretty_date_string)
        forecast = get_forecast()
        now = datetime.datetime.now(my_pytz)
        now_pretty = now.strftime(pretty_date_string)
        my_pretty_stop = pytz.utc.localize(stop_time).astimezone(my_pytz).strftime(pretty_date_string)
        return render_template('index.html', start_time=my_pretty_start, stop_time = my_pretty_stop, sundown = sundown_pretty, forecast = forecast, now = now_pretty)

@app.route('/start_now')
def start_now():
    start_magicblue()
    return '{"start_now": "ok"}'

@app.route('/stop_now')
def stop_now():
    stop_magicblue()
    return '{"stop_now": "ok"}'

## Shut the dajumn thing down
@app.route('/shutdown')
def shutdown():
    print("SHUT DOWN")
    os.system("/sbin/shutdown -h now")
    return redirect("/")

def throw_schedule():
    while True:
        schedule.run_pending()
        time.sleep(10)


## Init TZ
my_pytz = pytz.timezone(my_tz)

## Plan lights out every day at the set time
lightsout_time_struct = list((time.strptime(lightsout_hour, "%H:%M"))[:7])
lightsout_time = datetime.datetime(*lightsout_time_struct)
lightsout_time = my_pytz.localize(lightsout_time)
## A small problem. I assume the user entered the time in his own timezone.
## Schedule uses system time, which is in UTC. Let's fix this.
schedule.every().day.at(lightsout_time.astimezone(pytz.utc).strftime("%H:%M")).do(stop_magicblue)

## And plan the job that will figure out when to start the lamp 5 minutes after that
nextplanning = lightsout_time + datetime.timedelta(minutes=1)
schedule.every().day.at(nextplanning.astimezone(pytz.utc).strftime("%H:%M")).do(schedule_magicblue_start)

## Also, look at the current time and situation. If we are in "on" time, force the lamp
## ON time is defined as: "right now we're somewhere between sundown and lights out"
now = datetime.datetime.now(my_pytz)
lightson_time = get_lightson_utctime()

if(lightsout_time.time() > now.time() > lightson_time.time()):
    start_magicblue()
else:
    ## If it's not "ON" time then schedule an ON. After the first run, the lightsout scheduler will take over.
    schedule_magicblue_start()

thread = Thread(target = throw_schedule)
thread.daemon=True
thread.start()

app.debug = debug
app.run(host='0.0.0.0', port=port)
