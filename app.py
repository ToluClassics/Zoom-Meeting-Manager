from flask import Flask, request, session
import os
import jwt
import http.client
import datetime
import json
import re
from zoomus import ZoomClient
from twilio.twiml.messaging_response import MessagingResponse


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET")


API_KEY = os.environ.get('API_KEY')
API_SECRET = os.environ.get('API_SECRET')
EMAIL_ADDRESS = os.environ.get('USER_EMAIL')

#regex pattern for validating the time
regex_start_time = '[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}'

client = ZoomClient(API_KEY,API_SECRET)

#define a route for the application that supports POST requests
@app.route('/meeting', methods=['POST'])
def meeting():

    #convert incoming message to lower case and remove trailing whitespace
    in_msg = request.values.get('Body', '').strip().lower()
    resp = MessagingResponse()
    msg = resp.message()

    #List meetings
    if in_msg=='1' or 'one' in in_msg:
        reply = list_meetings(client,str(EMAIL_ADDRESS))
        msg.body(reply)
        return str(resp)
    
    #Create Meeting
    if (in_msg=='2' or 'two' in in_msg):
        session['next_reply'] = True
        session['request'] = 'Create'
        reply = ("To Schedule a Zoom Meeting, Provide the following information\n"
                "Provide Meeting Start Time 🕐 by following the format below:\n"
                "yyyy-MM-dd-HH-mm-ss Example: 2020-09-21-12-00-00")
        msg.body(reply)
        return str(resp)
    elif 'request' in session and session['request']=='Create':
        if session['next_reply'] == True: 
            if 'start_time' not in session:
                if (re.search(regex_start_time,in_msg)):
                    session['start_time'] = in_msg
                    reply = "Kindly provide the Meeting Topic or Agenda"
                    msg.body(reply)
                    return str(resp)
            if 'topic' not in session:
                session['topic'] = in_msg
                reply = "Kindly provide the duration of the meeting in minutes e.g 30"
                msg.body(reply)
                return str(resp)
            if 'duration' not in session:
                session['duration'] = in_msg
                session.pop('next_reply', None)
                session.pop('request', None)
            
                api_resp, meeting_info = create_meeting(session['topic'],session['start_time'], session['duration'], EMAIL_ADDRESS, session['topic'])
                session.pop('topic', None)
                session.pop('start_time', None)
                session.pop('duration', None)

                if api_resp.status_code == 201:
                    reply = ("Here You go:\n"
                            +"Meeting Join URL:  "+str(meeting_info['join_url'])
                            +"\nMeeting Topic:  "+str(meeting_info['topic'])
                            +"\nMeeting Agenda:  "+str(meeting_info['agenda'])
                            +"\nMeeting Password:  "+str(meeting_info['h323_password'])
                            +"\nMeeting Start URL:  "+str(meeting_info['start_url'])
                            )
                    msg.body(reply)
                    return str(resp)
                else:
                    reply = "Could not create meeting"
                    msg.body(reply)
                    return str(resp)


    #Delete Meeting
    if (in_msg=='3' or 'three' in in_msg):
        session['next_reply'] = True
        session['request'] = 'Delete'
        reply = "Kindly Provide the Meeting ID of the Meeting to be Deleted"
        msg.body(reply)
        return str(resp)
    elif 'request' in session and session['request']=='Delete':
        if session['next_reply'] == True:
            get_resp = get_meeting(client,in_msg,EMAIL_ADDRESS)
            if get_resp.status_code == 200:
                response_code = delete_meeting(client,in_msg,EMAIL_ADDRESS)
                print(session)
                session.pop('next_reply', None)
                session.pop('request', None)  
                if response_code.status_code == 204:
                    reply = "The meeting with id " + in_msg +" has been deleted"
                    msg.body(reply)
                    return str(resp)
                else:
                    reply = "The meeting with id " + in_msg +" Could not be deleted"
                    msg.body(reply)
                    return str(resp)


    if in_msg == 'hello' or in_msg == 'hi':
        reply = ("Hello!, I am your Zoom Meeting Manager\n"
                +"Kindly select One of the options below:\n"
                +"*1.)* List Scheduled Meetings\n"
                +"*2.)* Create a Meeting\n"
                +"*3.)* Delete a Meeting\n")
        msg.body(reply)
        return str(resp)

#Function to list user meetings
def list_meetings(client,user_id):
    data_dict = json.loads(client.meeting.list(user_id=user_id).content)

    meeting = ""

    if len(data_dict['meetings']) == 0:
        meeting = meeting + "There are no scheduled meetings"
    else:
        for i,dict in enumerate(data_dict['meetings']):
            meet_info = (str(i+1)+ ". Meeting Topic: "+str(dict['topic'])
                        +"\n   Meeting ID:  "+str(dict['id'])
                        +"\n   Meeting Start Time:  "+str(dict['start_time'])
                        +"\n   Meeting Timezone: "+str(dict['timezone'])
                    + "\n   Meeting Duration: "+str(dict['duration'])
                    + "\n   Meeting URL: " + dict['join_url']  
                        +"\n\n")
            meeting = meeting + meet_info
    return meeting

#Function to delete schedule meetings
def delete_meeting(client,meeting_id,host_id):
    delete_meet = client.meeting.delete(id=meeting_id,host_id=host_id)
    return delete_meet

def create_meeting(topic,start_time, duration, user_id, agenda):
    time_array = start_time.split('-')
    time_array = [int(i) for i in time_array] 
    time_dt = datetime.datetime(time_array[0],time_array[1],time_array[2],
                time_array[3],time_array[4],time_array[5])
    
    zoom_meeting=client.meeting.create(topic=topic, type=2, start_time=time_dt, 
                                        duration=duration, user_id=user_id, 
                                        agenda=topic, host_id=user_id)
    
    data_dict = json.loads(zoom_meeting.text)

    return zoom_meeting, data_dict

def get_meeting(client,meeting_id,host_id):
    meet_info = client.meeting.get(id=meeting_id,host_id=host_id)
    return meet_info


#define a function to generate the a response to the user when they send a wrong message
def initial_response():
    message =("Hello!, I am your Zoom Meeting Manager\n\n"
            "Kindly select One of the options below:\n"
             "*1.)* List Scheduled Meetings\n"
             "*2.)* Create a Meeting\n"
             "*3.)* Delete a Meeting\n")
    return message


if __name__ == "__main__":
    app.run(debug=True)

    



