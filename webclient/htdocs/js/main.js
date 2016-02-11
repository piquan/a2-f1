"use strict";

/* global io */
/* global Blockly */

var a2f1 = {
    rcons : {
        print_common : function(objlist, terminator) {
            // I can't just use objlist.map, because objlist is not
            // actually an Array object (when passed from "arguments").  I
            // need to make a new argument.
            var msgs = new Array(objlist.length);
            for(var i = 0; i < objlist.length; ++i) {
                msgs[i] = objlist[i].toString();
            }

            var msg = msgs.join(" ");
            console.log(msg);
            var consdiv = $("#console");
            consdiv.text(consdiv.text() + msg + terminator);
            consdiv.scrollTop(consdiv[0].scrollHeight);
        },
        terpri : function() {
            var consdiv = $("#console");
            var old_text = consdiv.text();
            if (! old_text.endsWith("\n"))
                consdiv.text(old_text + "\n");
        },
        princ : function() {
            this.print_common(arguments, "");
        },
        print : function() {
            this.print_common(arguments, "\n");
        },
        contents : function() {
            return $("#console").text();
        }
    },

    stopButtonClicked : function(evt) {
        $(evt.currentTarget).addClass("active");
        a2f1.socket.emit('button_clicked',
                         { name: evt.currentTarget.id },
                         function () {
                             $(evt.currentTarget).removeClass("active");
                             console.log("Button reset");
                         });
    },

    robot_uri : function() {
        var base = document.location;
        return base.protocol + "//" + base.host;
    },

    init : function() {
        var rcons = this.rcons;

        $("#stopButton").on('click', this.stopButtonClicked);

        var blocklyArea = document.getElementById('blocklyArea');
        var blocklyDiv = document.getElementById('blocklyDiv');
        this.workspace = Blockly.inject(
            blocklyDiv,
            {toolbox: document.getElementById('toolbox')});

        var onresize = function(e) {
            // Compute the absolute coordinates and dimensions of blocklyArea.
            var element = blocklyArea;
            var x = 0;
            var y = 0;
            do {
                x += element.offsetLeft;
                y += element.offsetTop;
                element = element.offsetParent;
            } while (element);
            // Position blocklyDiv over blocklyArea.
            blocklyDiv.style.left = x + 'px';
            blocklyDiv.style.top = y + 'px';
            blocklyDiv.style.width = blocklyArea.offsetWidth + 'px';
            blocklyDiv.style.height = blocklyArea.offsetHeight + 'px';
        };
        window.addEventListener('resize', onresize, false);
        onresize();

        console.log(rcons.contents());
        // This is the first message the user will see after the message
        // in index.html, which is "]]] Booting primary monitor control systems...".
        rcons.print(" active.");
        rcons.princ("]]] Connecting to A2-F1...");

        var connection_ever_ok = false;
        var connection_ok = false;
        var reconnect_error;
        var socket = io(this.robot_uri(),
                        { reconnectionAttempts: 4 });
        this.socket = socket;
        socket.on('connect', function (data) {
            connection_ok = true;
            connection_ever_ok = true;
            rcons.print(" connected.");
        });
        socket.on('error', function (reason) {
            rcons.terpri();
            rcons.print("]]] Unable to connect to A2-F1:", reason);
        });
        // Many of these "reconnecting" messages are emitted on errors on
        // the initial connection.
        socket.on('reconnecting', function (attempts) {
            if (connection_ok) {
                rcons.terpri();
                rcons.princ("]]] Connection to A2-F1 lost.  Attempting to reconnect...");
                connection_ok = false;
            }
        });
        socket.on('reconnect_failed', function () {
            if (connection_ever_ok) {
                rcons.print("]]] Failed to reconnect to A2-F1:", reconnect_error);
            } else {
                rcons.terpri();
                rcons.print("]]] Failed to connect to A2-F1:", reconnect_error);
            }
            rcons.print("]]] Connection offline.");
        });
        socket.on('reconnect_error', function (reason) {
            console.log(reason);
            reconnect_error = reason;
        });

        socket.on('console', function (data) {
            rcons.print(data.message);
        });
        
        this.imgsocket = io(this.robot_uri() + "/cam");
        this.imgsocket.on('image', function (data) {
            $("#cam").attr("src", data.url);
        });
    }
};

$(function(){a2f1.init();});