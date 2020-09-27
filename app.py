from flask import Flask, request, session
from dotenv import load_dotenv
import os
import jwt
import http.client
import datetime
import json
import re
from twilio.twiml.messaging_response import MessagingResponse

load_dotenv()
#session.clear()


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET")


API_KEY = os.environ.get('API_KEY')
API_SECRET = os.environ.get('API_SECRET')

#regex pattern for validating email
regex_email = '^[a-z0-9]+[\._]?[a-z0-9]+[@]\w+[.]\w{2,3}$'

#regex pattern for validating the time
regex_start_time = '[0-9]{4}-[0-9]{2}-[0-9]{2}t[0-9]{2}:[0-9]{2}:[0-9]{2}z'

#Timezones
timezone = ['Africa/Bangui','Etc/Greenwich','Europe/London','Asia/Tokyo','America/New_York']


#define a route for the application that supports POST requests
@app.route('/meeting', methods=['POST'])
def meeting():
    #convert incoming message to lower case and remove trailing whitespace
    in_msg = request.values.get('Body', '').strip().lower()
    resp = MessagingResponse()
    msg = resp.message()

    correct_response = False
    session['token'] = generate_token(1)

    print(session)

    #First Response from the User
    if ('email' in session) and (re.search(regex_email,in_msg)) and session['request']=="":
        session['email'] = in_msg
        correct_response = True
        reply = ("Select One of the Options below:\n"
             "*1.)* List Meetings\n"
             "*2.)* Create a Meeting\n"
             "*3.)* Delete a Meeting\n")
        msg.body(reply)
        return str(resp)

    #Second Response From the User
    if ('email' in session) and ('list' in in_msg or in_msg == '1' or 'one' in in_msg) and ('fourth_response' not in session):
        session['request'] = ""
        correct_response = True
        reply = list_meetings(session['token'],session['email'],page_size=5)
        msg.body(reply)
        session.pop('second_response', None)
        session.pop('first_response', None)
        return str(resp)
    elif ('email' in session) and ('create' in in_msg or in_msg == '2' or 'two' in in_msg) and ('fourth_response' not in session):
        session['request'] = 'create'
        correct_response = True
        session['first_response'] = True
        reply = ("To Schedule a Zoom Meeting, Provide the following information\n"
                "Provide Meeting Start Time 🕐 by following the format below:\n"
                "yyyy-MM-ddTHH:mm:ssZ Example: 2020-09-21T12:00:00Z")
        msg.body(reply)
        return str(resp)
    elif ('email' in session) and ('delete' in in_msg == '3' in in_msg or 'three' in in_msg) and ('fourth_response' not in session):
        session['request'] = 'delete'
        correct_response = True
        session['first_response'] = True
        reply = "Kindly Provide the Meeting ID of the Meeting to be Deleted"
        msg.body(reply)
        return str(resp)

    #Third Response From the User
    if ('email' in session) and ('request' in session) and ('first_response' in session) :
        if session['first_response'] == True and session['request'] == 'delete':
            session['meeting_id'] = in_msg
            #validate the meeting id
            if get_meeting(session['meeting_id'],session['token']) == 200:
                session['second_response'] = True
                session['first_response'] = False
                session['meeting_id'] = in_msg
                reply = "Are you sure you want to delete meeting: " + str(session['meeting_id']
                        +"\n Kindly reply with Yes or No")
                msg.body(reply)
                return str(resp)
            else: 
                reply = "The Meeting ID provided is incorrect"
                session.pop('second_response', None)
                session.pop('first_response', None)
                msg.body(reply)
                return str(resp)
        elif session['first_response'] == True and session['request'] == 'create':
            if (re.search(regex_start_time,in_msg)):
                session['start_time'] = in_msg
                reply = "Kindly provide the Meeting Topic or Agenda"
                session['second_response'] = True
                session.pop('first_response', None)
                correct_response = True
                msg.body(reply)
                return str(resp)
            
    
    #Fourth Response
    if ('email' in session) and ('second_response' in session):
        if session['second_response'] == True and session['request'] == 'delete':
            if 'yes' in in_msg:
                response_code = delete_meeting(session['meeting_id'],session['token'])
                if response_code == 204:
                    reply = "The meeting: " + str(session['meeting_id'] +" has been deleted")
                    msg.body(reply)
                    session.pop('second_response', None)
                    return str(resp)
                else:
                    reply = "The meeting: " + str(session['meeting_id'] +" Could not be deleted")
                    msg.body(reply)
                    session['second_response'] = False
                    session['request'] = ""
                    return str(resp)
            else:
                reply = "The meeting: " + str(session['meeting_id'] +" would not be deleted")
                msg.body(reply)
                session['second_response'] = False
                return str(resp)
        elif session['second_response'] == True and session['request'] == 'create':
            session['third_response'] = True
            session.pop('second_response', None)
            correct_response = True
            session['Topic'] = in_msg
            reply = "Kindly provide the duration of the meeting in minutes e.g 30"
            msg.body(reply)
            return str(resp)
    
    #Fifth Response
    if ('email' in session) and ('third_response' in session):
        if session['third_response'] == True and session['request'] == 'create':
            session['fourth_response'] = True
            session.pop('third_response', None)
            session['Duration'] = int(in_msg)
            reply = ("Kindly select one of the timezones below by replying with a number\n"
                    "1.) West Central Africa\n"
                    "2.) Greenwich Mean Time\n"
                    "3.) Europe/London Timezone\n"
                    "4.) Osaka, Sapporo, Tokyo\n"
                    "5.) Eastern Time (US and Canada)\n")
            msg.body(reply)
            return str(resp)
    
    #Sixth Response
    if ('email' in session) and ('fourth_response' in session):
        session['fifth_response'] = True
        session.pop('fourth_response', None)
        session['timezone'] = timezone[int(in_msg)-1]
        print(session['timezone'])
        api_resp, meeting_info = create_meeting(session['token'],session['Topic'],session['start_time'],session['Duration'],session['timezone'],session['email'])
        if api_resp == 201:
            reply = ("Here You fo:\n"
                     "Meeting Join URL:  "+str(meeting_info['join_url'])
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

        

    #Introductory Message or Intro
    if ('hello' in in_msg or 'hi' in in_msg) or (not correct_response):
        reply = ("Hi!, This is Your Zoom Meeting 🤝 Manager\n\n"
                "Kindly Provide your email Address\n")    
        msg.body(reply)
        session['email'] = ""
        session['request'] = ""
        try:
            session.pop('second_response', None)
            session.pop('first_response', None)
            session.pop('third_response', None)
            session.pop('fourth_response', None)
        except:
            pass
        print(session)
        return str(resp)


#function to generate bearer token for authentication
def generate_token(hours):
    
    payload = {
            'iss': API_KEY,
            'exp': datetime.datetime.now() + datetime.timedelta(hours=hours)
            }
    jwt_encoded = str(jwt.encode(payload, API_SECRET), 'utf-8')
    return jwt_encoded


#define a function to generate the a response to the user when they send a wrong message
def wrong_response():
    message =("Hi!, You have entered an incorrect message\n\n"
            "Select One of the Options below:\n"
             "*1.)* List Meetings\n"
             "*2.)* Create a Meeting\n"
             "*3.)* Delete a Meeting\n")
    return message

#Define a function to return a list of meetings for a particular user
def list_meetings(token,user_id,page_size=5):
    conn = http.client.HTTPSConnection("api.zoom.us")

    headers = {'authorization': 'Bearer %s' % token}

    conn.request("GET", "/v2/users/%s/meetings?page_size=%s&type=scheduled"%(user_id,page_size), 
                headers=headers)
    
    res = conn.getresponse()
    data = res.read()
    data_decoded=data.decode("utf-8")
    data_dict = json.loads(data_decoded)

    meeting = ""

    for i,dict in enumerate(data_dict['meetings']):
        meet_info = (str(i+1)+ ". Meeting Topic: "+str(dict['id'])
                     +"\n   Meeting ID:  "+str(dict['id'])
                    +"\n   Meeting Start Time:  "+str(dict['start_time'])
                    +"\n   Meeting Timezone: "+str(dict['timezone'])
                   + "\n   Meeting Duration: "+str(dict['duration'])
                   + "\n   Meeting URL: " + dict['join_url']  
                    +"\n\n")
        meeting = meeting + meet_info
    
    return meeting

#Define a function to check if a meeting exists
def get_meeting(meeting_id,token):
    conn = http.client.HTTPSConnection("api.zoom.us")
    headers = {'authorization': 'Bearer %s' % token}

    conn.request("GET", "/v2/meetings/%s"%(meeting_id), headers=headers)
    res_code = conn.getresponse().status

    return res_code

#Define a function to delete a meeting
def delete_meeting(meeting_id,token):
    conn = http.client.HTTPSConnection("api.zoom.us")
    headers = {'authorization': 'Bearer %s' % token}

    conn.request("DELETE", "/v2/meetings/%s"%(meeting_id), headers=headers)
    res_code = conn.getresponse().status

    return res_code

#Define a function for creating a meeting
def create_meeting(token, topic,start_time,duration,timezone,email):
    conn = http.client.HTTPSConnection("api.zoom.us")
    headers = {'content-type': 'application/json','authorization': 'Bearer %s' % token}

    start_time = start_time.replace("t","T").replace("z","Z")
    payload = "{\"topic\":\"%s\",\"type\":2,\"start_time\":\"%s\",\"duration\":%s,\"timezone\":\"%s\",\"agenda\":\"%s\"}"%(topic.capitalize(),start_time,duration,timezone,topic.capitalize())

    conn.request("POST", "/v2/users/%s/meetings"%email, payload, headers)
    res = conn.getresponse()
    data = res.read()

    data_decoded=data.decode("utf-8")
    data_dict = json.loads(data_decoded)

    status = res.status
    return status, data_dict



if __name__ == "__main__":
    app.run(debug=True)