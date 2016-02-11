'use strict';

var ws = require('ws');

exports.installHandler = 
function(http_server, camimgurl, cammgrpath, clientsockio) {
    new CamHandler(http_server, camimgurl, cammgrpath, clientsockio);
};

function CamHandler(http_server, camimgurl, cammgrpath, clientsockio) {
    this.cammgrserver = new ws.Server({server: http_server, path:cammgrpath});
    this.clientsockio = clientsockio;
    this.camimgurl = camimgurl;
    this.client_count = 0;
    this.managers = new Array();
    this.cammgrserver.on('connection', this.onManagerConnect.bind(this));
    this.clientsockio.on('connection', this.onClientConnect.bind(this));
    // We periodically send a client count as a ping to all the managers,
    // to prevent nginx from exceeding proxy_read_timeout.  (In the current
    // camdaemon implementation, we don't actually connect through nginx,
    // but it's still relevant.)  We could use a websocket ping message,
    // but may as well send a small client count message in case we failed
    // to update it properly another time.
    setInterval(this.broadcastClientCount.bind(this), 50000).unref();
}

CamHandler.prototype.toString = function() {
    return 'CamHandler object with ' + this.client_count + ' clients';
};

//
// Manager connections
//
// The manager is a regular WebSockets connection from a daemon running
// locally.  We use a much simpler protocol than socket.io, since
// the available socket.io Python implementations are difficult to use,
// and we don't need the full flexibility of socket.io.
//
// The camera daemon sends us JSON-encoded packets of the form:
//   {image:'foo.jpg'}
// We only get the filename, and are responsible for making it a usable URL
// for the clients.
//
// We send to the camera daemon JSON-encoded packets:
//   {client_count:3}
// We send the client count so that the camera daemon can power down the
// camera when there are no clients connected.

CamHandler.prototype.broadcastClientCount = function() {
    console.log('Client count:', this.client_count);
    var msg = JSON.stringify({client_count: this.client_count});
    this.managers.forEach(function (mgr) { mgr.send(msg); });
};

CamHandler.prototype.managerIsAcceptable = function(websocket) {
    var req = websocket.upgradeReq;
    return (req.socket.remoteAddress === '127.0.0.1' &&
            (!('x-forwarded-for' in req.headers) ||
             req.headers['x-forwarded-for'] === '127.0.0.1'));
};

CamHandler.prototype.onManagerConnect = function(websocket, callback) {
    console.log('Manager connect');
    if (!this.managerIsAcceptable(websocket)) {
        console.log('Fake manager disconnected');
        websocket.terminate();
        return;
    }
    this.managers.push(websocket);
    websocket.on('message', this.onManagerMessage.bind(this, websocket));
    websocket.on('error', this.onManagerError.bind(this, websocket));
    websocket.on('close', this.onManagerClose.bind(this, websocket));
    this.broadcastClientCount();
};

CamHandler.prototype.onManagerMessage = function(websocket, data, flags) {
    //console.log('Manager:', data);
    var data_obj = JSON.parse(data);
    if ("image" in data_obj) {
        this.sendClientImage(this.camimgurl + data_obj.image);
    }
};

CamHandler.prototype.onManagerError = function(websocket, error) {
    console.log('Manager error:', error);
    this.removeManager(websocket);
};

CamHandler.prototype.onManagerClose = function(websocket, code, message) {
    console.log('Manager disconnect:', code, message);
    this.removeManager(websocket);
};

CamHandler.prototype.removeManager = function(websocket) {
    var mgridx = this.managers.indexOf(websocket);
    if (mgridx != -1)
        this.managers.splice(mgridx, 1);
};

//
// Client handling functions
//
// The clients are using a socket.io connection in the /cam namespace.
// We send images as messages of the form
//    image{url:'/cam/img/foo.jpg'}
// We don't listen for any messages.

CamHandler.prototype.onClientConnect = function(socket) {
    console.log('New client connected:', socket.id);
    this.client_count++;
    socket.on('error', this.onClientError.bind(this));
    socket.on('disconnect', this.onClientClose.bind(this));
    this.broadcastClientCount();
};

CamHandler.prototype.onClientError = function(socket, error) {
    console.log('Client error:', error);
    this.client_count--;
    this.broadcastClientCount();
};

CamHandler.prototype.onClientClose = function(socket) {
    console.log('Client disconnect:', socket.id);
    this.client_count--;
    this.broadcastClientCount();
};

CamHandler.prototype.sendClientImage = function(imageUrl) {
    this.clientsockio.volatile.emit('image', {'url': imageUrl});
};
