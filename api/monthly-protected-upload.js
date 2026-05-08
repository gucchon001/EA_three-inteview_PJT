'use strict';

/**
 * 送付エクスポート用: 暗号化 HTML を Vercel Blob に置き、公開 URL を JSON で返す。
 * 環境変数 BLOB_READ_WRITE_TOKEN（Vercel ダッシュボードで Blob ストア連携時に付与）が必須。
 */
const { put } = require('@vercel/blob');
const crypto = require('crypto');

const MAX_BYTES = 12 * 1024 * 1024;

function requestOrigin(req) {
    try {
        var host = req.headers['x-forwarded-host'] || req.headers.host;
        if (!host || typeof host !== 'string') return '';
        var protoHdr = req.headers['x-forwarded-proto'];
        var proto = 'https';
        if (protoHdr && typeof protoHdr === 'string') {
            proto = protoHdr.split(',')[0].trim() || proto;
        }
        return proto + '://' + host.split(',')[0].trim();
    } catch (e) {
        return '';
    }
}

function readBody(req) {
    if (req.body != null && typeof req.body === 'string') {
        return Promise.resolve(req.body);
    }
    return new Promise(function (resolve, reject) {
        var chunks = [];
        var len = 0;
        req.on('data', function (c) {
            len += c.length;
            if (len > MAX_BYTES) {
                reject(new Error('too_large'));
                return;
            }
            chunks.push(c);
        });
        req.on('end', function () {
            resolve(Buffer.concat(chunks).toString('utf8'));
        });
        req.on('error', reject);
    });
}

module.exports = async function monthlyProtectedUpload(req, res) {
    if (req.method === 'OPTIONS') {
        res.setHeader('Access-Control-Allow-Origin', '*');
        res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
        res.setHeader('Access-Control-Allow-Headers', 'Content-Type, X-MR-Original-Name');
        return res.status(204).end();
    }
    if (req.method !== 'POST') {
        res.setHeader('Allow', 'POST');
        return res.status(405).json({ ok: false, error: 'Method not allowed' });
    }
    var token = process.env.BLOB_READ_WRITE_TOKEN;
    if (!token) {
        return res.status(503).json({
            ok: false,
            error: 'BLOB_READ_WRITE_TOKEN が未設定です。Vercel の Project → Storage → Blob を有効化してください。',
        });
    }
    var html;
    try {
        html = await readBody(req);
    } catch (e) {
        if (e && e.message === 'too_large') {
            return res.status(413).json({ ok: false, error: 'Body too large' });
        }
        return res.status(400).json({ ok: false, error: 'Invalid body' });
    }
    if (!html || html.length < 32) {
        return res.status(400).json({ ok: false, error: 'Empty or too short' });
    }
    var id = crypto.randomBytes(14).toString('hex');
    var pathname = 'monthly-protected/' + id + '.html';
    try {
        var blob = await put(pathname, html, {
            access: 'public',
            token: token,
            contentType: 'text/html; charset=utf-8',
        });
        var origin = requestOrigin(req);
        /** Blob 直リンクは HTML が attachment になるため、インライン表示用 URL を送る */
        var deliveryUrl =
            origin !== '' ? origin + '/api/monthly-protected-inline?id=' + id : blob.url;
        res.setHeader('Content-Type', 'application/json; charset=utf-8');
        return res.status(200).json({ ok: true, url: deliveryUrl });
    } catch (e) {
        console.error('monthly-protected-upload', e);
        return res.status(500).json({ ok: false, error: 'Upload failed' });
    }
};
