#!/usr/bin/env python

"""
Server for realtime Galaxy communication.


At first you need to install a few requirements.

. GALAXY_ROOT/.venv/bin/activate    # activate Galaxy's virtualenv
pip install flask flask-socketio eventlet   # install the requirements



As a next step start the communication server with something like this:

./scripts/communication_server.py --port 7070 --host localhost

Please make sure the host and the port matches the ones on config/galaxy.ini

The communication server feature of Galaxy can be controlled on three different levels:
  1. Admin can activate/deactivate communication (config/galaxy.ini)
  2. User can actrivate/deactivate for one session (in the communication window)
  3. User can actrivate/deactivate as personal-setting for ever (Galaxy user preferences)


"""


import sys
import argparse
from flask import Flask, request, make_response, current_app
from flask_socketio import SocketIO, emit, disconnect, join_room, leave_room, close_room, rooms
from datetime import timedelta
from functools import update_wrapper

app = Flask(__name__)
app.config['SECRET_KEY'] = 'notscret'
socketio = SocketIO(app)


# Taken from flask.pocoo.org/snippets/56/

def crossdomain(origin=None, methods=None, headers=None,
                max_age=21600, attach_to_all=True,
                automatic_options=True):
    if methods is not None:
        methods = ', '.join(sorted(x.upper() for x in methods))
    if headers is not None and not isinstance(headers, basestring):
        headers = ', '.join(x.upper() for x in headers)
    if not isinstance(origin, basestring):
        origin = ', '.join(origin)
    if isinstance(max_age, timedelta):
        max_age = max_age.total_seconds()

    def get_methods():
        if methods is not None:
            return methods

        options_resp = current_app.make_default_options_response()
        return options_resp.headers['allow']

    def decorator(f):
        def wrapped_function(*args, **kwargs):
            if automatic_options and request.method == 'OPTIONS':
                resp = current_app.make_default_options_response()
            else:
                resp = make_response(f(*args, **kwargs))
            if not attach_to_all and request.method != 'OPTIONS':
                return resp

            h = resp.headers

            h['Access-Control-Allow-Origin'] = origin
            h['Access-Control-Allow-Methods'] = get_methods()
            h['Access-Control-Max-Age'] = str(max_age)
            if headers is not None:
                h['Access-Control-Allow-Headers'] = headers
            return resp

        f.provide_automatic_options = False
        return update_wrapper(wrapped_function, f)
    return decorator


template = """<!DOCTYPE HTML>
<html>
<head>
   <title>Chat</title>
   <link rel="stylesheet" type="text/css" href="http://netdna.bootstrapcdn.com/bootstrap/3.0.0/css/bootstrap.min.css">
    <style>
    html, body {
        height: 100%;
        font-size: 13px;
    }
    /* Styles for message text box */
    .clearable{
      background: #fff url(http://i.stack.imgur.com/mJotv.gif) no-repeat right -10px center;
      border: 1px solid #999;
      padding: 3px 18px 3px 4px;
      border-radius: 3px;
      transition: background 0.4s;
    }
    .clearable.x  { background-position: right 5px center; }
    .clearable.onX{ cursor: pointer; }
    .clearable::-ms-clear {display: none; width:0; height:0;}
    .size-message {
        height: 60px;
        width: 99.5%;
        margin-top: 2px;
    }
    /* Styles for top right icons */
    .right_icons {
        margin-left: 92%;
        position: fixed;
    }
    #chat_tabs,
    #txtbox_chat_room {
        margin-top: 2px;
        margin-left: 2px;
    }
    ul, li,
    .user,
    .anchor {
        cursor: pointer;
        color: black;
    }
    .messages {
        overflow-y: auto;
        height: 100%;
        margin-left: 2px;
    }
    .send_message {
        margin-top: 5px;
        margin-left: 2px;
    }
    .user_name {
        font-style: italic;
    }
    .user_message {
        background-color: #DFE5F9;
        width: 99%;
    }
    .date_time {
        font-style: italic;
        font-size: 12px;
    }
    .date_time span {
        float: right;
    }
    .tab-content {
        height: 65%;
    }
    .tab-pane {
        height: 100%;
    }

    ul>li i {
        padding-left: 4px;
        font-size: 12px;
    }
    </style>
</head>
<body style="overflow: hidden; height: 100%";>
    <div class="right_icons">
        <i id="online_status" class="anchor fa fa-comments" aria-hidden="true" title=""></i>
        <i id="chat_history" class="anchor fa fa-history" aria-hidden="true" title="Show chat history"></i>
        <!-- <i id="group_chat" class="anchor fa fa-users" aria-hidden="true" title=""></i> -->
        <i id="clear_messages" class="anchor fa fa-trash-o" aria-hidden="true" title="Clear all messages"></i>
    </div>
    <ul class="nav nav-tabs" id="chat_tabs">
        <li class="active">
            <a data-target="#all_chat_tab" data-toggle="tab" aria-expanded='true'>All Chats</a>
        </li>
        <li>
            <a data-target="#chat_room_tab" data-toggle="tab" aria-expanded='false'>Chat Room</a>
        </li>
    </ul>
    <div class="tab-content">
        <div class="tab-pane active fade in" id="all_chat_tab">
            <div id="all_messages" class="messages"></div>
        </div>
    <div class="tab-pane fade" id="chat_room_tab">
            <div id="join_room">
                <input id="txtbox_chat_room" type="text" class="chat-room-textbx" value="" placeholder="Enter room name to join...">
            </div>
            <!-- <div id="all_messages_room" class="messages"></div> -->
        </div>
    </div>
    <div class="send_message">
        <textarea id="send_data" class="size-message clearable" placeholder="Type your message...">
        </textarea>
    </div>

    <script type="text/javascript" src="https://code.jquery.com/jquery-1.10.2.js"></script>
    <script type="text/javascript" src="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.6/js/bootstrap.min.js"></script>
    <script type="text/javascript" src="//cdnjs.cloudflare.com/ajax/libs/socket.io/1.3.5/socket.io.min.js"></script>
    <script src="https://use.fontawesome.com/89a733ecb7.js"></script>
    <script type="text/javascript" charset="utf-8">
    // the namespace events connect to
    var namespace = '/chat',
    socket = io.connect( window.location.protocol + '//' + document.domain + ':' + location.port + namespace);
    // socketio events
    var events_module = {
        // event handler for sent data from server
        event_response: function( socket ) {
            socket.on('event response', function( msg ) {
                var orig_message = msg.data.split(':'),
                    message = "",
                    uid = utils.get_userid(),
                    $el_all_messages = $('#all_messages'),
                    $el_tab_li = $( "a[data-target='#all_chat_tab']" );
                // builds the message to be displayed
                message = utils.build_message( orig_message, uid );
                // append only for non empty messages
                if( orig_message[0].length > 0 ) {
                    utils.append_message( $el_all_messages, message );
                    // adding message to build full chat history
                    if( !localStorage[uid] ) {
                        localStorage[uid] = message + '<br>';
                    }
                    else {
                        localStorage[uid] = localStorage[uid] + message + '<br>';
                    }
                }
                // updates the user session storage with all the messages
                sessionStorage[uid] = $el_all_messages.html();
                // show the last item by scrolling to the end
                utils.scroll_to_last( $el_all_messages );
                if( uid !== orig_message[1].split('-')[1] ) {
                    utils.show_notification( $el_tab_li );
                }
           });
       },
       // event handler for room messages
       event_response_room: function( socket ) {
           socket.on('event response room', function( msg ) {
               var $el_all_messages = $( '#all_messages' ),
                   message = '',
                   uid = utils.get_userid(),
                   tab_counter = 0,
                   $el_tab_li = null;
               // response when user joins
               if( msg.userjoin ) {
                   message = msg.userjoin.split("-")[0] + " has joined " + msg.data + ":" + msg.userjoin;
                   utils.append_message( $el_all_messages, utils.build_message( message.split(":"), uid ) );
                   utils.scroll_to_last( $el_all_messages );
                   if( uid !== msg.userjoin.split('-')[1] ) {
                       $el_tab_li = $( "a[data-target='#all_chat_tab']" );
                       utils.show_notification( $el_tab_li );
                   }
               } // response when user leaves
               else if( msg.userleave ) {
                   message = msg.userleave.split("-")[0] + " has left " + msg.data + ":" + msg.userleave;
                   utils.append_message( $el_all_messages, utils.build_message( message.split(":"), uid ) );
                   utils.scroll_to_last( $el_all_messages );
                   if( uid !== msg.userleave.split('-')[1] ) {
                       $el_tab_li = $( "a[data-target='#all_chat_tab']" );
                       utils.show_notification( $el_tab_li );
                   }
               }
               else { // normal message sharing when connected
                   for(var counter = 0; counter < click_events.connected_room.length; counter++) {
                       if(msg.chatroom === click_events.connected_room[counter]) {
                           tab_counter = counter;
                           break;
                       }
                   };
                   $el_room_msg = $( "#all_messages_" + tab_counter );
                   utils.append_message( $el_room_msg, utils.build_message( msg.data.split(':'), uid ) );
                   utils.scroll_to_last( $el_room_msg );
                   if( uid !== msg.data.split(':')[1].split('-')[1] ) {
                       $el_tab_li = $( "a[data-target='#tabroom_" + tab_counter + "'" + " ]" );
                       utils.show_notification( $el_tab_li );
                   }
               }
           });
        },
        // event handler for new connections
        event_connect: function( socket ) {
            socket.on( 'connect', function() {
                var send_data = { };
                send_data.data = 'connected' + ':' + utils.get_username();
                socket.emit( 'event connect', send_data );
            });
        }
    }
    // all the click events of buttons
    var click_events = {
        // on form load, user is connected, so the value is true
        is_connected: true,
        active_tab: "#all_chat_tab",
        connected_room: [],
        tab_id_number: 0,
        broadcast_data: function( socket ) {
            $('#send_data').keydown(function( event ) {
                if( click_events.is_connected ) {
                    var send_data = {},
                        tab_counter = 0,
                        event_name = "";
                    if( event.keyCode == 13 || event.which == 13 ) {
                        // if the tab is all chats
                        if( click_events.active_tab === '#all_chat_tab' ) {
                            send_data.data = escape( $( '#send_data' ).val() ) + ':' + utils.get_userdata();
                            event_name = 'event broadcast';
                        }
                        else { // if the tab belongs to room
                            tab_counter = $('.nav-tabs>li.active').children().attr("data-target").split('_')[1];
                            send_data.data = escape( $( '#send_data' ).val() ) + ':' + utils.get_userdata();
                            send_data.room = click_events.connected_room[tab_counter];
                            event_name = 'event room';
                        }
                        socket.emit( event_name, send_data );
                        $( '#send_data' ).val( '' );
                        return false;
                    }
                }
            });
        },
        // sets the current active tab
        active_element: function() {
            $('.nav-tabs>li').click(function( e ){
                click_events.active_tab = e.target.attributes['data-target'].nodeValue;
                $(this).children().css('background-color', '');
                // hides the message textarea for create room tab
                if( $(this).children().attr("data-target") === "#chat_room_tab" ) {
                    $( '#send_data' ).css( 'display', 'none' );
                }
                else {
                     $( '#send_data' ).css( 'display', 'block' );
                }
            });
        },
        // event for connected and disconneted states
        connect_disconnect: function( socket ) {
            $( '#online_status' ).click(function() {
                var $el_online_status = $( '#online_status' ),
                    $el_input_text = $( '#send_data' ),
                    send_data = { }
                    connected_message = 'Type your message...',
                    uid = utils.get_userid();
                if( click_events.is_connected ) {
                    click_events.make_disconnect( uid, $el_input_text, $el_online_status );
                }
                else {
                    socket.connect();
                    click_events.is_connected = true;
                    sessionStorage['connected'] = true;
                    utils.update_online_status( $el_online_status, click_events.is_connected );
                    $el_input_text.prop( 'disabled', false );
                    $el_input_text.val( '' );
                    $el_input_text.prop( 'placeholder', connected_message );
                }
            });
        },
        // clear all the messages
        clear_messages: function() {
        $( '#clear_messages' ).click(function( event ) {
                // clears all the messages
                utils.clear_message_area();
                return false;
            });
        },
        // shows full chat history
        show_chat_history: function() {
            $( '#chat_history' ).click( function( events ) {
                utils.fill_messages( localStorage[utils.get_userid()] );
            });
        },
        // delete full history
        delete_history: function() {
            $( '#delete_history' ).click( function() {
                var uid = utils.get_userid();
                localStorage.removeItem(uid);
                sessionStorage.removeItem( uid );
                utils.clear_message_area();
            });
        },
        // makes disconnect
        make_disconnect: function( uid, $el_input_text, $el_online_status ) {
            var send_data = {}
                disconnected_message = 'You are now disconnected. To send/receive messages, please connect';
            click_events.is_connected = false;
            send_data.data = "disconnected" + ":" + utils.get_username();
            socket.emit( 'event disconnect', send_data );
            sessionStorage.removeItem( uid );
            sessionStorage['connected'] = false;
            utils.update_online_status( $el_online_status, click_events.is_connected );
            $el_input_text.val( '' );
            $el_input_text.prop( 'placeholder', disconnected_message );
            $el_input_text.prop( 'disabled', true );
        },
        // for creating/joining chat room
        create_chat_room: function( socket ) {
            var $el_txtbox_chat_room = $( '#txtbox_chat_room' ),
                tab_room_header_template = "",
                tab_room_body_template = "",
                tab_id = "",
                self = this;
            $el_txtbox_chat_room.keydown(function( e ) {
                if( e.which === 13 || e.keyCode === 13 ) {
                    socket.emit('join', { room: $el_txtbox_chat_room.val(), userjoin: utils.get_userdata() });
                    self.connected_room.push( $el_txtbox_chat_room.val() );

                    // removes the active class from the chat creating tab
                    $( '#chat_room_tab' ).removeClass( 'fade active in' ).addClass( 'fade' );
                    $( 'ul>li.active' ).removeClass( 'active' );

                    // sets new tab id
                    tab_id = "tabroom_" + self.tab_id_number;

                    // create chat room tab header for new room
                    tab_room_header_template = "<li class='active'><a data-target=" + "#" + tab_id + " data-toggle='tab' aria-expanded='false'>" + self.connected_room[self.connected_room.length-1] + "<i class='fa fa-times anchor close-room' title='Close room'></i></a></li>";
                    $( '#chat_tabs' ).append( tab_room_header_template );

                    // create chat room tab body for new room
                    tab_room_body_template = "<div class='tab-pane active fade in' id=" + tab_id + "><div id='all_messages_" + self.tab_id_number + "'" + " class='messages'></div></div>";
                    $( '.tab-content' ).append( tab_room_body_template );
                    self.leave_close_room();
                    self.active_element();
                    $el_txtbox_chat_room.val("");
                    self.tab_id_number++;
                    // displays the textarea
                    $( '#send_data' ).css( 'display', 'block' );
                    return false;
                }
            });
        },
        // for chat rooms/ group chat
        leave_close_room: function() {
            var tab_counter = "";
            $( '.close-room' ).click(function( e ) {
                e.stopPropagation();
                tab_counter = $(this).parent().attr('data-target').split("_")[1];
                // leaves room
                socket.emit('leave', {room: click_events.connected_room[tab_counter], userleave: utils.get_userdata() });
                // removes tab and its content
                $('.tab-content ' + $(this).parent().attr('data-target')).remove();
                $(this).parent().parent().remove();
                // selects the last tab and makes it active
                $('#chat_tabs a:last').tab('show');
                // hides or shows textarea
                if( $('#chat_tabs a:last').attr("data-target") === "#chat_room_tab" ) {
                    $( '#send_data' ).css( 'display', 'none' );
                }
                else {
                     $( '#send_data' ).css( 'display', 'block' );
                }
                return false;
            });
        },
    }
    // utility methods
    var utils = {
        // get the current username of logged in user
        // from the querystring of the URL
        get_userdata: function() {
            var $el_modal_body = $('.modal-body'),
                user_data = $el_modal_body.context.URL.split('?')[1],
                data = user_data.split('&'),
                userid_data = data[1],
                username_data = data[0];
                if( data ) {
                    return unescape( username_data.split('=')[1] + "-" + userid_data.split('=')[1] );
                }
                else {
                   return "";
               }
        },
        // fill in all messages
        fill_messages: function ( collection ) {
            var uid = utils.get_userid(),
            message_html = $.parseHTML( collection ),
            $el_all_messages = $('#all_messages');
            // clears the previous items
            this.clear_message_area();
            if(collection) {
                $el_all_messages.append( $( '<div' + '/' + '>' ).html( message_html ) );
            }
            // show the last item by scrolling to the end
            utils.scroll_to_last($el_all_messages);
        },
        // gets the user id
        get_userid: function() {
            return utils.get_userdata().split('-')[1];
        },
        // gets the user name
        get_username: function() {
            return utils.get_userdata().split('-')[0];
        },
        // scrolls to the last of element
        scroll_to_last: function( $el ) {
            if( $el[0] ) {
                $el.scrollTop( $el[0].scrollHeight );
            }
        },
        // append message
        append_message: function( $el, message ) {
            $el.append( message );
            $el.append( '<br>' );
        },
        // builds message
        build_message: function(original_message, uid) {
            var from_uid = original_message[1].split('-')[1],
                message_user = "",
                message_text = "";
            // for user's own messages
            if ( from_uid === uid ) {
                message_user = this.build_message_username_template( 'me' );
            }
            // for other user's messages
            else {
                message_user = this.build_message_username_template( unescape( original_message[1].split('-')[0] ) );
            }
            message_text = this.build_message_template( original_message );
            return message_user + message_text;
        },
        // builds message template
        build_message_template: function( original_message ) {
            return "<div class='user_message'>" + unescape( original_message[0] ) +
                       "<div class='date_time'><span title=" + this.get_date() + ">" + this.get_time() + "</span>" +
                   "</div></div>";
        },
        // builds template for username for message display
        build_message_username_template: function( username ) {
            return "<span class='user_name'>" + username + "<br></span>";
        },
        // adds an information about the online status
        update_online_status: function( $el, connected ) {
            if( connected ) {
                $el.prop( "title", "You are online!" ).css( "color", "#00FF00" );
            }
            else {
                $el.prop( "title", "You are offline!" ).css( "color", "#FF0000");
            }
        },
        // gets the current date and time
        get_time: function() {
            var currentdate = new Date(),
                datetime = "",
                hours = 0,
                minutes = 0;
                hours = ( currentdate.getHours() < 10 ) ? ( "0" + currentdate.getHours() ) : currentdate.getHours();
                minutes = ( currentdate.getMinutes() < 10 ) ? ( "0" + currentdate.getMinutes() ) : currentdate.getMinutes();
                datetime = hours + ":" + minutes;
                return datetime;
        },
        get_date: function() {
            var currentdate = new Date(),
                day,
                month;
            month = ( (currentdate.getMonth()+1 ) < 10) ? ( "0" + (currentdate.getMonth()+1) ) : ( currentdate.getMonth()+1 );
            day = ( currentdate.getDate() < 10 ) ? ( "0" + currentdate.getDate() ) : currentdate.getDate();
            return month + "/" + day + "/" + currentdate.getFullYear();
        },
        set_user_info: function() {
            $( '.user' ).prop( 'title', this.get_username() );
        },
        clear_message_area: function() {
            $('#all_messages').html("");
        },
        show_notification: function( $el ) {
            if( !$el.parent().hasClass('active') ) {
                $el.css('background-color', '#FCD116');
                for (var i = 2; i >= 1; i--) { 
                    $el.fadeOut(200).fadeIn(200);
                }
            } 
        },
    }
    // this snippet is for adding a clear icon in the message textbox
    function tog(v){return v?'addClass':'removeClass';}
    $(document).on('input', '.clearable', function(){
        $(this)[tog(this.value)]('x');
    }).on('mousemove', '.x', function( e ){
        $(this)[tog(this.offsetWidth-18 < e.clientX-this.getBoundingClientRect().left)]('onX');
    }).on('touchstart click', '.onX', function( ev ){
        ev.preventDefault();
        $(this).removeClass('x onX').val('').change();
    });
    // registers the events when this document is ready
        $(document).ready(function(){
            // fill the messages if user is already connected
            // and comes back to the chat window
            var uid = utils.get_userid();
            utils.fill_messages(sessionStorage[uid]);
            // updates online status text
            // by checking if user was connected or not
            if(sessionStorage['connected']) {
                if(sessionStorage['connected'] === 'true' || sessionStorage['connected'] === true) {
                    utils.update_online_status( $('#online_status'), true );
                    click_events.is_connected = true;
                }
                else {
                    click_events.make_disconnect( uid, $('#send_data'), $('#online_status') );
                    utils.clear_message_area();
                }
            }
            else {
                utils.update_online_status( $('#online_status'), true );
                click_events.is_connected = true;
            }
            // set user info to the user icon
            utils.set_user_info();
            // registers response event
            events_module.event_response(socket);
            // registers room response event
            events_module.event_response_room(socket);
            // registers connect event
            events_module.event_connect(socket);
            // registers create room event
            click_events.create_chat_room(socket);
            // broadcast the data
            click_events.broadcast_data(socket);
            // disconnet the user from the chat server
            click_events.connect_disconnect(socket);
            // show chat history
            click_events.show_chat_history();
            // clears all the messages
            click_events.clear_messages();
            // deletes full chat history
            click_events.delete_history();
            click_events.active_element();
            click_events.leave_close_room();
            //utils.get_time();
            utils.scroll_to_last( $('#all_messages') );
            // build tabs
            $('#chat_tabs').tab();
            $('#send_data').val("");
       });
    </script>
</body>
</html>"""


@app.route('/')
@crossdomain(origin='*')
def index():
    return template


@socketio.on('event connect', namespace='/chat')
def event_connect(message):
    print("connected")


@socketio.on('event broadcast', namespace='/chat')
def event_broadcast(message):
    emit('event response',
         {'data': message['data']}, broadcast=True)


@socketio.on('event disconnect', namespace='/chat')
def event_disconnect(message):
    print("disconnected")
    disconnect()


@socketio.on('disconnect', namespace='/chat')
def event_disconnect():
    print("disconnected")


@socketio.on('join', namespace='/chat')
def join(message):
    join_room(message['room'])
    emit('event response room', {'data': message['room'], 'userjoin': message['userjoin']}, broadcast=True)


@socketio.on('leave', namespace='/chat')
def leave(message):
    leave_room(message['room'])
    emit('event response room',
         {'data': message['room'], 'userleave': message['userleave']}, broadcast=True)


@socketio.on('event room', namespace='/chat')
def send_room_message(message):
    emit('event response room',
         {'data': message['data'], 'chatroom': message['room']}, room=message['room'])

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Real-time communication server for Galaxy.')
    parser.add_argument('--port', type=int, default="7070", help='Port number on which the server should run.')
    parser.add_argument('--host', default='localhost', help='Hostname of the communication server.')

    args = parser.parse_args()
    socketio.run(app, host=args.host, port=args.port)

