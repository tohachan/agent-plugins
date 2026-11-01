import http from 'node:http';
export function createApi(db) {
  return http.createServer(async (req, res) => {
    const route = /^\/orders\/(\d+)$/.exec(req.url);
    if (req.method !== 'GET' || !route) { res.writeHead(404).end(); return; }
    const user = req.headers['x-user-id'];
    if (typeof user !== 'string' || !user) { res.writeHead(401).end(); return; }
    try {
      const { rows } = await db.query('SELECT id, status FROM orders WHERE id=$1 AND user_id=$2', [route[1], user]);
      if (!rows.length) { res.writeHead(404).end(); return; }
      res.setHeader('Content-Type', 'application/json'); res.end(JSON.stringify(rows[0]));
    } catch { res.writeHead(500).end(); }
  });
}
// Caller starts this server at 0.0.0.0:8080 inside the API container.
