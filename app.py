from flask import Flask, request, session
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv
from zoomus import ZoomClient
import os
import datetime
import json
import re
import pytz


# Import environmental variables
load_dotenv()


app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET")


API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
EMAIL_ADDRESS = os.getenv('USER_EMAIL')

# regex pattern for validating the time
regex_start_time = r"[0-9]{4}-[0-9]{2}-[0-9]{2}\s[0-9]{2}:[0-9]{2}:[0-9]{2}"
# Create Zoom Client
client = ZoomClient(API_KEY, API_SECRET)


# define a route for the application that supports POST
# requests
@app.route("/meeting", methods=["POST"])
def meeting():

    # convert incoming message to lower case and remove
    # trailing whitespace
    in_msg = request.values.get("Body", "").strip().lower()
    resp = MessagingResponse()
    msg = resp.message()

    # List meetings
    if in_msg == "1" or "one" in in_msg:
        reply = list_meetings(client, str(EMAIL_ADDRESS))
        msg.body(reply)
        return str(resp)

    # Create Meeting
    if in_msg == "2" or "two" in in_msg:
        session["request"] = "Create"
        reply = (
            "To Schedule a Zoom Meeting, Provide the following information\n"
            "Provide Meeting Start Time 🕐 by following the format below:\n"
            "yyyy-MM-dd HH:mm:ss Example: 2020-09-21 12:00:00")
        msg.body(reply)
        return str(resp)
    elif "request" in session and session["request"] == "Create":
        if "start_time" not in session:
            if re.search(regex_start_time, in_msg):
                session["start_time"] = in_msg
                reply = "Kindly provide the Meeting Topic or Agenda"
                msg.body(reply)
                return str(resp)
        elif "topic" not in session:
            session["topic"] = in_msg
            reply = "Kindly provide the duration of the meeting in minutes e.g 30"
            msg.body(reply)
            return str(resp)
        elif "duration" not in session:
            session.pop("request", None)
            api_resp, meeting_info = create_meeting(
                session["topic"],
                session["start_time"],
                in_msg,
                EMAIL_ADDRESS,
                session["topic"],
            )
            session.pop(request, None)
            if api_resp.status_code == 201:
                reply = ("Here You go:\n" +
                         "Meeting ID:  " +str(meeting_info["id"]) +
                         "\nMeeting Join URL:  " +str(meeting_info["join_url"]) +
                         "\nMeeting Topic:  " +str(meeting_info["topic"]) +
                         "\nMeeting Agenda:  " +str(meeting_info["agenda"]) +
                         "\nMeeting Start Time:  " +session["start_time"]+
                         "\nMeeting Password:  " +str(meeting_info["h323_password"]) +
                         "\nMeeting Start URL:  " +str(meeting_info["start_url"]))
                msg.body(reply)
                session.pop("topic", None)
                session.pop("start_time", None)
                return str(resp)
            else:
                reply = "Could not create meeting"
                msg.body(reply)
                return str(resp)

    # Delete Meeting
    if in_msg == "3" or "three" in in_msg:
        session["request"] = "Delete"
        reply = "Kindly Provide the Meeting ID of the Meeting to be Deleted"
        msg.body(reply)
        return str(resp)
    elif "request" in session and session["request"] == "Delete":
        get_resp = get_meeting(
            client, in_msg, EMAIL_ADDRESS)
        if get_resp.status_code == 200:
            response_code = delete_meeting(
                client, in_msg, EMAIL_ADDRESS)
            session.pop("request", None)
            if response_code.status_code == 204:
                reply = "The meeting with id " + \
                    in_msg + " has been deleted"
                msg.body(reply)
                return str(resp)
            else:
                reply = "The meeting with id " + \
                    in_msg + " Could not be deleted"
                msg.body(reply)
                return str(resp)
        else:
            reply = "The meeting with id " + in_msg + " does not exist"
            msg.body(reply)
            return str(resp)

    if in_msg == "hello" or in_msg == "hi":
        reply = initial_response()
        msg.body(reply)
        return str(resp)

    reply = " You have entered an invalid reply \n" + \
        initial_response()
    msg.body(reply)
    session.pop("request", None)
    return str(resp)


#Add a function to convert time from one timezone to another
def convert_timezone(time_input,old_timezone,new_timezone):
    time_array = time_input.split(' ')
    day = time_array[0].split('-')
    meeting_time = time_array[1].split(':')

    day = [int(i) for i in day]
    meeting_time = [int(i) for i in meeting_time]

    time_dt = datetime.datetime(day[0],day[1],day[2],
        meeting_time[0],meeting_time[1],meeting_time[2])

    old_timezone = pytz.timezone(old_timezone)
    new_timezone = pytz.timezone(new_timezone)

    conv_date = old_timezone.localize(time_dt).astimezone(new_timezone)

    return conv_date

# Function to list user meetings
def list_meetings(client, user_id):
    data_dict = json.loads(client.meeting.list(user_id=user_id).content)

    meeting = ""

    if len(data_dict["meetings"]) == 0:
        meeting = meeting + "There are no scheduled meetings"
    else:
        for i, dict in enumerate(data_dict["meetings"]):
            timezone = str(dict["timezone"])
            meeting_time_gmt = str(dict["start_time"]).replace("T", " ").replace("Z", " ")
            meeting_time_exact = convert_timezone(meeting_time_gmt,timezone,'GMT').ctime()
            meet_info = (
                str(i+1) +
                " Meeting Topic: " +str(dict["topic"]) +
                "\n   Meeting ID:  " +str(dict["id"]) +
                "\n   Meeting Start Time:  " +meeting_time_exact +
                "\n   Meeting Timezone: " +timezone +
                "\n   Meeting Duration: " +str(dict["duration"]) +
                "\n   Meeting URL: " +dict["join_url"] +
                "\n\n"
                )
            meeting += meet_info
            #account for the twilio 1600 character limit
            if len(meeting) > 1600:
                meeting.rstrip(meet_info)
                break
    return meeting


# Function to delete schedule meetings
def delete_meeting(client, meeting_id, host_id):
    delete_meet = client.meeting.delete(id=meeting_id, host_id=host_id)
    return delete_meet


def create_meeting(topic,start_time,duration,user_id,agenda):

    timezone = json.loads(client.user.get(id=EMAIL_ADDRESS).text)['timezone']
    newest_time = convert_timezone(start_time,timezone,'GMT')

    zoom_meeting = client.meeting.create(
        topic=topic,
        type=2,
        start_time=newest_time,
        duration=duration,
        user_id=user_id,
        agenda=topic,
        timezone=timezone,
        host_id=user_id)

    data_dict = json.loads(zoom_meeting.text)

    return zoom_meeting, data_dict

def get_meeting(client, meeting_id, host_id):
    meet_info = client.meeting.get(id=meeting_id, host_id=host_id)
    return meet_info

# define a function to generate a response to user to kickstart the conversation
def initial_response():
    message = (
        "Hello!, I am your Zoom Meeting Manager\n\n"
        "Kindly select One of the options below:\n"
        "*1.)* List Scheduled Meetings\n"
        "*2.)* Create a Meeting\n"
        "*3.)* Delete a Meeting\n"
    )
    return message

if __name__ == "__main__":
    app.run(debug=True)
