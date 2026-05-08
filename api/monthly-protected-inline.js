'use strict';

/**
 * Vercel Blob は HTML を attachment で配信するため、ブラウザが保存ダイアログになる。
 * 同一プロジェクトの Blob（monthly-protected/{id}.html）だけを取得し inline で返す。
 */
const { get } = require('@vercel/blob');
const { Readable } = require('stream');

const ID_RE = /^[a-f0-9]{28}$/i;

function streamToBuffer(webStream) {
    var node = Readable.fromWeb(webStream);
    return new Promise(function (resolve, reject) {
        var chunks = [];
        node.on('data', function (c) {
            chunks.push(c);
        });
        node.on('end', function () {
            resolve(Buffer.concat(chunks));
        });
        node.on('error', reject);
    });
}

module.exports = async function monthlyProtectedInline(req, res) {
    if (req.method !== 'GET' && req.method !== 'HEAD') {
        res.setHeader('Allow', 'GET, HEAD');
        return res.status(405).end();
    }
    var token = process.env.BLOB_READ_WRITE_TOKEN;
    if (!token) {
        return res.status(503).send('BLOB_READ_WRITE_TOKEN is not configured.');
    }
    var rawUrl;
    try {
        rawUrl = new URL(req.url, 'http://localhost');
    } catch (e) {
        return res.status(400).send('Bad request');
    }
    var id = rawUrl.searchParams.get('id');
    if (!id || !ID_RE.test(id)) {
        return res.status(400).send('Invalid or missing id');
    }
    var pathname = 'monthly-protected/' + id.toLowerCase() + '.html';
    try {
        var result = await get(pathname, { access: 'public', token: token });
        if (!result || result.statusCode !== 200 || !result.stream) {
            return res.status(404).send('Not found');
        }
        var ct = (result.blob && result.blob.contentType) || 'text/html; charset=utf-8';
        res.setHeader('Content-Type', ct);
        res.setHeader('Content-Disposition', 'inline; filename="monthly_report_protected.html"');
        res.setHeader('Cache-Control', 'public, max-age=60');
        if (req.method === 'HEAD') {
            return res.status(200).end();
        }
        var body = await streamToBuffer(result.stream);
        return res.status(200).send(body);
    } catch (e) {
        console.error('monthly-protected-inline', e);
        return res.status(500).send('Internal error');
    }
};
