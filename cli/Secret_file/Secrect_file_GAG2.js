const http = require('http');
const net = require('net');
const { exec, spawn } = require('child_process');

const HOST = '127.0.0.1';
const DEFAULT_PORT = 43125;

let macroProcess = null;

function openInBrowser(url) {
	const safeUrl = `"${url}"`;

	if (process.platform === 'win32') {
		exec(`start "" ${safeUrl}`);
		return;
	}

	if (process.platform === 'darwin') {
		exec(`open ${safeUrl}`);
		return;
	}

	exec(`xdg-open ${safeUrl}`);
}

function openRoblox() {
	if (process.platform === 'win32') {
		exec('start "" "roblox://"');
		return;
	}

	throw new Error('Roblox launch helper is only implemented for Windows.');
}

function sendJson(res, statusCode, payload) {
	res.writeHead(statusCode, { 'Content-Type': 'application/json; charset=utf-8' });
	res.end(JSON.stringify(payload));
}

function readJsonBody(req) {
	return new Promise((resolve, reject) => {
		let body = '';

		req.on('data', (chunk) => {
			body += chunk;
			if (body.length > 1024 * 1024) {
				reject(new Error('Payload too large'));
				req.destroy();
			}
		});

		req.on('end', () => {
			if (!body) {
				resolve({});
				return;
			}

			try {
				resolve(JSON.parse(body));
			} catch (_err) {
				reject(new Error('Invalid JSON body'));
			}
		});

		req.on('error', reject);
	});
}

function escapeSingleQuotes(text) {
	return String(text || '').replace(/'/g, "''");
}

function startDesktopMacro(config) {
	if (process.platform !== 'win32') {
		throw new Error('Real desktop macro is only supported on Windows.');
	}

	if (macroProcess) {
		throw new Error('Macro is already running. Stop it before starting again.');
	}

	const windowTitle = escapeSingleQuotes(config.windowTitle || '');
	const harvestKey = escapeSingleQuotes(config.harvestKey || 'e');
	const buyKey = escapeSingleQuotes(config.buyKey || '');
	const harvestIntervalMs = Math.max(200, Number(config.harvestIntervalMs) || 1200);
	const buyEveryCycles = Math.max(0, Number(config.buyEveryCycles) || 0);
	const maxRuntimeSec = Math.max(5, Number(config.maxRuntimeSec) || 30);

	const psScript = [
		`$windowTitle = '${windowTitle}'`,
		`$harvestKey = '${harvestKey}'`,
		`$buyKey = '${buyKey}'`,
		`$harvestIntervalMs = ${harvestIntervalMs}`,
		`$buyEveryCycles = ${buyEveryCycles}`,
		`$maxRuntimeSec = ${maxRuntimeSec}`,
		'$wshell = New-Object -ComObject WScript.Shell',
		'function Focus-GameWindow {',
		'  param([string]$PreferredTitle)',
		'  if ($PreferredTitle -and $PreferredTitle.Trim().Length -gt 0) {',
		'    $ok = $wshell.AppActivate($PreferredTitle)',
		'    if ($ok) { return $true }',
		'  }',
		'  $candidate = Get-Process | Where-Object {',
		'    $_.MainWindowHandle -ne 0 -and $_.ProcessName -match "RobloxPlayerBeta|Roblox"',
		'  } | Sort-Object StartTime -Descending | Select-Object -First 1',
		'  if ($null -eq $candidate) {',
		'    $candidate = Get-Process | Where-Object {',
		'      $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -match "Roblox|Grow a Garden"',
		'    } | Sort-Object StartTime -Descending | Select-Object -First 1',
		'  }',
		'  if ($null -eq $candidate) { return $false }',
		'  return $wshell.AppActivate($candidate.Id)',
		'}',
		'$cycle = 0',
		'$misses = 0',
		'$stopAt = (Get-Date).AddSeconds($maxRuntimeSec)',
		'if ($windowTitle -and $windowTitle.Trim().Length -gt 0) {',
		'  Write-Output "Macro started with preferred window title: $windowTitle"',
		'} else {',
		'  Write-Output "Macro started with auto-detect mode (Roblox/Grow a Garden)."',
		'}',
		'Write-Output "Safety timeout: $maxRuntimeSec seconds"',
		'while ($true) {',
		'  if ((Get-Date) -ge $stopAt) {',
		'    Write-Output "Macro stopped by safety timeout."',
		'    break',
		'  }',
		'  $focused = Focus-GameWindow -PreferredTitle $windowTitle',
		'  if (-not $focused) {',
		'    $misses += 1',
		'    if ($misses % 10 -eq 0) {',
		'      Write-Output "Waiting for Roblox window... make sure the game is open and not minimized."',
		'    }',
		'    Start-Sleep -Milliseconds 500',
		'    continue',
		'  }',
		'  $misses = 0',
		'  Start-Sleep -Milliseconds 100',
		'  $wshell.SendKeys($harvestKey)',
		'  $cycle += 1',
		'  if ($buyKey -and $buyEveryCycles -gt 0 -and ($cycle % $buyEveryCycles -eq 0)) {',
		'    Start-Sleep -Milliseconds 80',
		'    $wshell.SendKeys($buyKey)',
		'  }',
		'  Start-Sleep -Milliseconds $harvestIntervalMs',
		'}',
	].join('\n');

	macroProcess = spawn(
		'powershell',
		['-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', psScript],
		{ stdio: ['ignore', 'pipe', 'pipe'] }
	);

	macroProcess.stdout.on('data', (data) => {
		const text = String(data || '').trim();
		if (text) {
			console.log(`[macro] ${text}`);
		}
	});

	macroProcess.stderr.on('data', (data) => {
		const text = String(data || '').trim();
		if (text) {
			console.error(`[macro-error] ${text}`);
		}
	});

	macroProcess.on('exit', () => {
		macroProcess = null;
	});
}

function stopDesktopMacro() {
	if (!macroProcess) {
		return false;
	}

	macroProcess.kill();
	macroProcess = null;
	return true;
}

function getHtml() {
	return `<!doctype html>
<html lang="en">
<head>
	<meta charset="utf-8" />
	<meta name="viewport" content="width=device-width, initial-scale=1" />
	<title>Grow a Garden 2 Macro Admin</title>
	<style>
		:root {
			--bg: #0a211f;
			--panel: #153430;
			--panel-2: #1f4a43;
			--accent: #ffd166;
			--accent-2: #9be564;
			--text: #f4fff8;
			--muted: #b5d8ca;
			--danger: #ff6b6b;
			--ok: #50d890;
		}

		* { box-sizing: border-box; }

		body {
			margin: 0;
			min-height: 100vh;
			font-family: "Trebuchet MS", "Segoe UI", sans-serif;
			color: var(--text);
			background:
				radial-gradient(circle at 20% 20%, #2f6f5f66 0%, transparent 40%),
				radial-gradient(circle at 80% 80%, #ffd16633 0%, transparent 35%),
				linear-gradient(135deg, #071715 0%, #0f2a26 45%, #1a3d38 100%);
			padding: 24px;
		}

		.wrap {
			max-width: 980px;
			margin: 0 auto;
			display: grid;
			gap: 18px;
			animation: fadeIn 350ms ease;
		}

		.hero {
			background: linear-gradient(145deg, #1e473f, #153430);
			border: 1px solid #3f7067;
			border-radius: 16px;
			padding: 20px;
			box-shadow: 0 8px 24px #00000035;
		}

		h1 {
			margin: 0 0 8px;
			font-size: clamp(1.4rem, 2.8vw, 2rem);
			letter-spacing: 0.5px;
		}

		p {
			margin: 0;
			color: var(--muted);
		}

		.grid {
			display: grid;
			grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
			gap: 16px;
		}

		.card {
			background: linear-gradient(180deg, var(--panel), var(--panel-2));
			border: 1px solid #4d7f75;
			border-radius: 14px;
			padding: 16px;
			box-shadow: 0 6px 18px #00000030;
		}

		.card h2 {
			margin: 0 0 12px;
			font-size: 1.1rem;
			color: var(--accent);
		}

		label {
			display: block;
			font-size: 0.92rem;
			margin: 10px 0 4px;
			color: #d6f4e7;
		}

		input, textarea, button {
			width: 100%;
			border-radius: 10px;
			border: 1px solid #6a958b;
			padding: 10px 12px;
			font-size: 0.95rem;
			color: #05201a;
			background: #f3fff8;
			outline: none;
		}

		textarea {
			min-height: 76px;
			resize: vertical;
			font-family: inherit;
		}

		button {
			margin-top: 12px;
			font-weight: 700;
			cursor: pointer;
			transition: transform 120ms ease, filter 120ms ease;
		}

		button:hover {
			transform: translateY(-1px);
			filter: brightness(1.03);
		}

		.primary {
			background: linear-gradient(90deg, var(--accent), #ffb703);
			color: #222;
			border-color: #ffc74f;
		}

		.save {
			background: linear-gradient(90deg, var(--accent-2), #67c653);
			color: #09220b;
			border-color: #9be564;
		}

		.stop {
			background: linear-gradient(90deg, #ff7a7a, #e34444);
			color: #2a0202;
			border-color: #ff9b9b;
		}

		.status {
			min-height: 20px;
			font-size: 0.9rem;
			margin-top: 8px;
			color: var(--ok);
		}

		.status.error {
			color: var(--danger);
		}

		.hint {
			margin-top: 8px;
			font-size: 0.88rem;
			color: #d2f5e6;
		}

		.secret-wrap {
			display: grid;
			gap: 10px;
			margin-top: 8px;
		}

		.secret-btn {
			max-width: 180px;
			margin-left: auto;
			background: #102925;
			color: #d8f7ea;
			border: 1px dashed #7db5a8;
		}

		.locked {
			display: none;
			animation: rise 220ms ease;
		}

		.dup-box {
			background: #0f2723;
			border: 1px solid #5c9d8f;
			border-radius: 12px;
			padding: 14px;
		}

		.mono {
			font-family: Consolas, monospace;
			color: #bff7d4;
			font-size: 0.9rem;
			margin-top: 8px;
			white-space: pre-wrap;
			word-break: break-word;
		}

		@keyframes fadeIn {
			from { opacity: 0; transform: translateY(6px); }
			to { opacity: 1; transform: translateY(0); }
		}

		@keyframes rise {
			from { opacity: 0; transform: translateY(8px); }
			to { opacity: 1; transform: translateY(0); }
		}
	</style>
</head>
<body>
	<main class="wrap">
		<section class="hero">
			<h1>Grow a Garden 2 Macro Admin</h1>
			<p>Runs on your PC and sends key presses to the live game window.</p>
		</section>

		<section class="grid">
			<article class="card">
				<h2>Auto Harvest</h2>
				<label for="harvestWeight">Weight to auto harvest (minimum)</label>
				<input id="harvestWeight" type="number" min="0" step="0.1" placeholder="Example: 2.5" />

				<label for="skipWeight">Weight you do NOT want to harvest</label>
				<input id="skipWeight" type="text" placeholder="Example: 0.2, 0.5, 1.0" />

				<label for="harvestItems">Optional item names to include</label>
				<textarea id="harvestItems" placeholder="Corn\nPumpkin\nBlueberry"></textarea>

				<button id="saveHarvest" class="save">Save Auto Harvest</button>
			</article>

			<article class="card">
				<h2>Auto Buy</h2>
				<label for="seedBuy">Seeds to auto buy</label>
				<textarea id="seedBuy" placeholder="Carrot Seed\nTomato Seed"></textarea>

				<label for="gearBuy">Gears to auto buy</label>
				<textarea id="gearBuy" placeholder="Watering Gear\nSpeed Gear"></textarea>

				<button id="saveBuy" class="save">Save Auto Buy</button>
			</article>
		</section>

		<section class="card">
			<h2>Macro Controls</h2>
			<label for="windowTitle">Preferred game window title (optional)</label>
			<input id="windowTitle" type="text" value="" placeholder="Leave empty to auto-detect Roblox window" />

			<label for="harvestKey">Harvest key</label>
			<input id="harvestKey" type="text" value="e" />

			<label for="buyKey">Buy key (optional)</label>
			<input id="buyKey" type="text" value="" placeholder="Leave blank to disable buy key" />

			<label for="harvestIntervalMs">Harvest delay (ms)</label>
			<input id="harvestIntervalMs" type="number" min="200" value="1200" />

			<label for="buyEveryCycles">Buy every X harvest cycles</label>
			<input id="buyEveryCycles" type="number" min="0" value="0" />

			<label for="maxRuntimeSec">Safety auto-stop (seconds)</label>
			<input id="maxRuntimeSec" type="number" min="5" value="30" />

			<button id="openRoblox" class="primary">Open Roblox App</button>
			<button id="runSearch" class="primary">Search "Grow a garden 2.macro"</button>
			<button id="startMacro" class="primary">Start Real Game Macro</button>
			<button id="stopMacro" class="stop">Stop Macro</button>
			<div class="hint">Keep Roblox open. This macro auto-detects Roblox or Grow a Garden windows and sends keys repeatedly.</div>
			<div id="status" class="status"></div>

			<div class="secret-wrap">
				<button id="secretBtn" class="secret-btn">Secret</button>

				<div id="secretPanel" class="locked dup-box">
					<strong>Duplication File</strong>
					<p style="margin:8px 0 10px; color:#b6dcd2;">Secret mode unlocked.</p>

					<label for="dupSource">Item name to duplicate</label>
					<input id="dupSource" type="text" placeholder="Example: Golden Carrot" />

					<label for="dupCount">Amount</label>
					<input id="dupCount" type="number" min="1" max="9999" value="1" />

					<button id="makeDup" class="primary">Generate Duplication File</button>
					<div id="dupOutput" class="mono"></div>
				</div>
			</div>
		</section>
	</main>

	<script>
		const statusEl = document.getElementById('status');

		function setStatus(msg, isError = false) {
			statusEl.textContent = msg;
			statusEl.classList.toggle('error', isError);
		}

		function getLines(value) {
			return value
				.split(/\r?\n/)
				.map((x) => x.trim())
				.filter(Boolean);
		}

		function saveState() {
			const payload = {
				harvestWeight: document.getElementById('harvestWeight').value,
				skipWeight: document.getElementById('skipWeight').value,
				harvestItems: document.getElementById('harvestItems').value,
				seedBuy: document.getElementById('seedBuy').value,
				gearBuy: document.getElementById('gearBuy').value,
				windowTitle: document.getElementById('windowTitle').value,
				harvestKey: document.getElementById('harvestKey').value,
				buyKey: document.getElementById('buyKey').value,
				harvestIntervalMs: document.getElementById('harvestIntervalMs').value,
				buyEveryCycles: document.getElementById('buyEveryCycles').value,
				maxRuntimeSec: document.getElementById('maxRuntimeSec').value,
			};

			localStorage.setItem('gag2_macro_admin', JSON.stringify(payload));
			return payload;
		}

		function loadState() {
			const raw = localStorage.getItem('gag2_macro_admin');
			if (!raw) return;

			try {
				const data = JSON.parse(raw);
				document.getElementById('harvestWeight').value = data.harvestWeight || '';
				document.getElementById('skipWeight').value = data.skipWeight || '';
				document.getElementById('harvestItems').value = data.harvestItems || '';
				document.getElementById('seedBuy').value = data.seedBuy || '';
				document.getElementById('gearBuy').value = data.gearBuy || '';
				document.getElementById('windowTitle').value = data.windowTitle || '';
				document.getElementById('harvestKey').value = data.harvestKey || 'e';
				document.getElementById('buyKey').value = data.buyKey || '';
				document.getElementById('harvestIntervalMs').value = data.harvestIntervalMs || '1200';
				document.getElementById('buyEveryCycles').value = data.buyEveryCycles || '0';
				document.getElementById('maxRuntimeSec').value = data.maxRuntimeSec || '30';
			} catch (err) {
				console.error(err);
			}
		}

		document.getElementById('saveHarvest').addEventListener('click', () => {
			const payload = saveState();
			const harvestItems = getLines(payload.harvestItems);
			setStatus(
				'Auto Harvest saved. Min weight: ' +
					(payload.harvestWeight || 'none') +
					', included items: ' +
					(harvestItems.length || 0)
			);
		});

		document.getElementById('saveBuy').addEventListener('click', () => {
			const payload = saveState();
			const seeds = getLines(payload.seedBuy).length;
			const gears = getLines(payload.gearBuy).length;
			setStatus('Auto Buy saved. Seeds: ' + seeds + ', Gears: ' + gears + '.');
		});

		document.getElementById('runSearch').addEventListener('click', async () => {
			setStatus('Opening web search...');
			try {
				const resp = await fetch('/search', { method: 'POST' });
				if (!resp.ok) throw new Error('Search request failed');
				setStatus('Browser search opened for: Grow a garden 2.macro');
			} catch (err) {
				setStatus('Could not open search: ' + err.message, true);
			}
		});

		document.getElementById('openRoblox').addEventListener('click', async () => {
			setStatus('Opening Roblox...');
			try {
				const resp = await fetch('/open-roblox', { method: 'POST' });
				const data = await resp.json();
				if (!resp.ok) throw new Error(data.error || 'Could not open Roblox');
				setStatus(data.message || 'Roblox launch requested.');
			} catch (err) {
				setStatus('Could not open Roblox: ' + err.message, true);
			}
		});

		document.getElementById('startMacro').addEventListener('click', async () => {
			const payload = saveState();
			setStatus('Starting live game macro...');
			try {
				const resp = await fetch('/start-macro', {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify(payload),
				});

				const data = await resp.json();
				if (!resp.ok) throw new Error(data.error || 'Could not start macro');
				setStatus(data.message || 'Macro started.');
			} catch (err) {
				setStatus(err.message, true);
			}
		});

		document.getElementById('stopMacro').addEventListener('click', async () => {
			setStatus('Stopping macro...');
			try {
				const resp = await fetch('/stop-macro', { method: 'POST' });
				const data = await resp.json();
				if (!resp.ok) throw new Error(data.error || 'Could not stop macro');
				setStatus(data.message || 'Macro stopped.');
			} catch (err) {
				setStatus(err.message, true);
			}
		});

		document.getElementById('secretBtn').addEventListener('click', () => {
			const code = prompt('Enter Secret Code');
			if (code === null) return;

			if (code.trim() === '9645') {
				document.getElementById('secretPanel').style.display = 'block';
				setStatus('Secret unlocked. Duplication file is now available.');
			} else {
				setStatus('Wrong code.', true);
			}
		});

		document.getElementById('makeDup').addEventListener('click', () => {
			const item = document.getElementById('dupSource').value.trim();
			const amount = Number(document.getElementById('dupCount').value || 1);

			if (!item) {
				setStatus('Please enter an item for duplication.', true);
				return;
			}

			const dupData = {
				mode: 'duplication',
				createdAt: new Date().toISOString(),
				item,
				amount,
			};

			document.getElementById('dupOutput').textContent = JSON.stringify(dupData, null, 2);
			setStatus('Duplication file generated in the panel.');
		});

		loadState();
	</script>
</body>
</html>`;
}

async function serveApp(req, res) {
	if (req.url === '/search' && req.method === 'POST') {
		openInBrowser('https://www.google.com/search?q=Grow+a+garden+2.macro');
		res.writeHead(204);
		res.end();
		return;
	}

	if (req.url === '/open-roblox' && req.method === 'POST') {
		try {
			openRoblox();
			sendJson(res, 200, { message: 'Roblox launch requested. Join your game, then click Start Real Game Macro.' });
		} catch (err) {
			sendJson(res, 400, { error: err.message || 'Could not open Roblox' });
		}
		return;
	}

	if (req.url === '/start-macro' && req.method === 'POST') {
		try {
			const body = await readJsonBody(req);
			startDesktopMacro(body);
			sendJson(res, 200, {
				message:
					'Real desktop macro started. Keep Roblox open. Auto-detect mode is active unless you set a preferred title.',
			});
		} catch (err) {
			sendJson(res, 400, { error: err.message || 'Could not start macro' });
		}
		return;
	}

	if (req.url === '/stop-macro' && req.method === 'POST') {
		const stopped = stopDesktopMacro();
		sendJson(res, 200, {
			message: stopped ? 'Macro stopped.' : 'Macro was not running.',
		});
		return;
	}

	if (req.url === '/' && req.method === 'GET') {
		res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
		res.end(getHtml());
		return;
	}

	res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
	res.end('Not Found');
}

const server = http.createServer((req, res) => {
	serveApp(req, res).catch((err) => {
		console.error(err);
		sendJson(res, 500, { error: 'Unexpected server error' });
	});
});

function findAvailablePort(startPort) {
	return new Promise((resolve, reject) => {
		function tryPort(port) {
			const probe = net.createServer();

			probe.once('error', (err) => {
				probe.close();
				if (err && err.code === 'EADDRINUSE') {
					tryPort(port + 1);
					return;
				}
				reject(err);
			});

			probe.once('listening', () => {
				probe.close(() => resolve(port));
			});

			probe.listen(port, HOST);
		}

		tryPort(startPort);
	});
}

async function startServer() {
	try {
		const openPort = await findAvailablePort(DEFAULT_PORT);
		if (openPort !== DEFAULT_PORT) {
			console.warn(`Port ${DEFAULT_PORT} is busy. Using ${openPort}.`);
		}

		server.listen(openPort, HOST, () => {
			const panelUrl = `http://${HOST}:${openPort}/`;

			console.log('Grow a Garden 2 Macro Admin is running.');
			console.log(`Panel: ${panelUrl}`);

			openInBrowser('https://www.google.com/search?q=Grow+a+garden+2.macro');
			openInBrowser(panelUrl);
		});
	} catch (err) {
		console.error(err);
		process.exit(1);
	}
}

startServer();

process.on('SIGINT', () => {
	stopDesktopMacro();
	server.close(() => {
		process.exit(0);
	});
});
