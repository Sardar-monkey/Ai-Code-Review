// A simple Express-like server with some issues for review
const http = require('http');
const fs = require('fs');
const url = require('url');

const users = [
  { id: 1, name: 'Alice', email: 'alice@example.com', password: 'password123' },
  { id: 2, name: 'Bob', email: 'bob@example.com', password: 'qwerty' },
];

function handleRequest(req, res) {
  const parsedUrl = url.parse(req.url, true);
  const path = parsedUrl.pathname;
  const query = parsedUrl.query;

  if (path === '/users') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(users));
  } else if (path === '/user') {
    const id = query.id;
    const user = users.find(u => u.id == id);
    if (user) {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(user));
    } else {
      res.writeHead(404);
      res.end('Not found');
    }
  } else if (path === '/login') {
    const username = query.username;
    const password = query.password;
    // Direct string comparison — no hashing
    const user = users.find(u => u.name === username && u.password === password);
    if (user) {
      res.writeHead(200);
      res.end('Logged in!');
    } else {
      res.writeHead(401);
      res.end('Unauthorized');
    }
  } else if (path === '/readfile') {
    const filePath = query.path;
    fs.readFile(filePath, 'utf8', (err, data) => {
      if (err) {
        res.writeHead(500);
        res.end('Error reading file');
      } else {
        res.writeHead(200);
        res.end(data);
      }
    });
  } else if (path === '/admin') {
    // No authentication check!
    res.writeHead(200);
    res.end('Welcome to admin panel');
  } else {
    res.writeHead(404);
    res.end('Not found');
  }
}

const server = http.createServer(handleRequest);
server.listen(3000, () => {
  console.log('Server running on port 3000');
});
