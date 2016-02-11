"use strict";

var http = require('http');
var config = require('config');
var express = require('express');
var socket_io = require('socket.io');
var cam = require('./cam.js');

function logRequestMiddleware (request, response, next) {
    console.log("]]] Web request:", request.originalUrl);
    next();
}
function send404 (request, response) {
    response.writeHead(404, {'Content-Type': 'text/plain'});
    response.end('404 Not Found');
}

function handleErr(err, response) {
    if (err) {
        response.writeHead(500, {'Content-Type': 'text/plain'});
        response.end(err.toString());
        return true;
    }
    return false;
}

function onConnection(socket) {
    console.log("New connection", socket.id,
                "from", socket.conn.request.headers['x-forwarded-for']);
    socket.emit('console', { message: 'A2-F1 simulator online.' });
    socket.on('button_clicked', function (data, callback) {
        socket.emit('console', { message: 'Button ' + data.name + ' clicked' });
        console.log("Button", data.name, "clicked");
        setTimeout(callback, 1000);
    });
}
    
exports.init = function() {
    var app = express();
    var http_server = http.Server(app);

    // Set up Express routing.  Which we currently don't really use.
    app.use(logRequestMiddleware);
    app.all('*', send404);

    // Set up socket.io.
    var io = socket_io(http_server);
    io.on('connection', onConnection);

    // Set up the camera handler.  This will watch on ws:/cam/mgr
    // and on the socket.io /cam namespace, and send pointers to clients
    // to the /cam/img/ URL space.
    cam.installHandler(http_server, "/cam/img/", "/cam/mgr", io.of("/cam"));

    // Activate the server.  We normally only listen on 127.0.0.1,
    // since we rely on nginx to listen on the public port and
    // redirect accordingly.
    var ip = config.get('cpanel_ip');
    var port = config.get('cpanel_port');
    http_server.listen(port, ip);
    console.log('Server running on http://' + ip + ':' + port);
};
