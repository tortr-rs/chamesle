// the board on chess.html. chess.js knows the rules, stockfish picks its moves, this draws the board
// and passes moves between them. click a piece, then where it goes.
import { Chess } from './chess.js';

const $ = (id) => document.getElementById(id);
const boardEl = $('board'), statusEl = $('status'), movesEl = $('moves');

// how hard stockfish tries, easiest first. skill is stockfish's own 0 to 20 setting
const LEVELS = [
	{ skill: 0, depth: 1, time: 100 },
	{ skill: 4, depth: 4, time: 250 },
	{ skill: 9, depth: 8, time: 500 },
	{ skill: 15, depth: 14, time: 900 },
	{ skill: 20, depth: 22, time: 1500 },
];
// the pieces are Cburnett's drawings, the ones on wikipedia: pieces/wk.svg is the white king and so on
const NAME = { k: 'king', q: 'queen', r: 'rook', b: 'bishop', n: 'knight', p: 'pawn' };

let game = new Chess();
let you = 'w';          // which side you play
let flipped = false;    // board drawn from black's side
let picked = null;      // the square you clicked first
let thinking = false;   // stockfish is choosing a move
let ask = 0;            // the request that counts right now
const sent = [];        // every request still waiting for its bestmove, oldest first
let ready = false;

function remember(k, v) { try { localStorage.setItem('chess-' + k, v); } catch (e) { /* private window, fine */ } }
function recall(k) { try { return localStorage.getItem('chess-' + k); } catch (e) { return null; } }

// the engine runs in a worker so the page doesn't freeze while it thinks
const engine = new Worker(new URL('./stockfish-19-lite-single.js', import.meta.url));
engine.onmessage = (ev) => {
	const line = typeof ev.data === 'string' ? ev.data : '';
	if (line === 'uciok') engine.postMessage('isready');
	else if (line === 'readyok' && !ready) { ready = true; update(); maybeEngine(); }
	// stockfish answers every go exactly once and in order, even the stopped ones
	else if (line.startsWith('bestmove')) answer(line.split(' ')[1], sent.shift());
};
engine.onerror = () => { statusEl.textContent = "Stockfish didn't load. Try reloading the page."; };
engine.postMessage('uci');

function maybeEngine() {
	if (!ready || thinking || game.isGameOver() || game.turn() === you) return;
	const lv = LEVELS[Number($('level').value)];
	thinking = true;
	sent.push(++ask);
	engine.postMessage('setoption name Skill Level value ' + lv.skill);
	engine.postMessage('position fen ' + game.fen());
	engine.postMessage('go depth ' + lv.depth + ' movetime ' + lv.time);
	update();
}

function answer(uci, id) {
	if (id !== ask || !thinking) return;   // a move for a game that's gone
	thinking = false;
	if (uci && uci !== '(none)') {
		try { game.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] || 'q' }); } catch (e) { /* can't happen, but don't die */ }
	}
	update();
}

function stopEngine() {
	ask++;
	if (thinking) engine.postMessage('stop');
	thinking = false;
}

function click(sq) {
	if (!ready || thinking || game.isGameOver() || game.turn() !== you) return;
	const piece = game.get(sq);
	if (picked && picked !== sq) {
		const legal = game.moves({ square: picked, verbose: true }).filter((m) => m.to === sq);
		if (legal.length) {
			game.move({ from: picked, to: sq, promotion: legal[0].promotion ? $('promo').value : undefined });
			picked = null;
			update();
			setTimeout(maybeEngine, 150);
			return;
		}
	}
	// pick up one of your own pieces, or put it back down
	picked = piece && piece.color === you && picked !== sq ? sq : null;
	update();
}

function draw() {
	const last = game.history({ verbose: true }).slice(-1)[0];
	const targets = picked ? game.moves({ square: picked, verbose: true }).map((m) => m.to) : [];
	const checked = game.inCheck() ? findKing(game.turn()) : null;
	const files = 'abcdefgh';
	boardEl.textContent = '';
	for (let row = 0; row < 8; row++) {
		for (let col = 0; col < 8; col++) {
			const f = flipped ? 7 - col : col, r = flipped ? row : 7 - row;
			const sq = files[f] + (r + 1);
			const p = game.get(sq);
			const b = document.createElement('button');
			b.type = 'button';
			b.className = 'sq ' + ((f + r) % 2 ? 'light' : 'dark');
			if (sq === picked) b.classList.add('picked');
			if (last && (sq === last.from || sq === last.to)) b.classList.add('last');
			if (targets.includes(sq)) b.classList.add(p ? 'take' : 'to');
			if (sq === checked) b.classList.add('check');
			if (p) {
				const img = document.createElement('img');
				img.src = new URL('./pieces/' + p.color + p.type + '.svg', import.meta.url);
				img.alt = '';
				img.draggable = false;
				b.appendChild(img);
			}
			b.setAttribute('aria-label', sq + (p ? ', ' + (p.color === 'w' ? 'white ' : 'black ') + NAME[p.type] : ''));
			// the letters and numbers along the edges
			if (row === 7) b.appendChild(label('file', files[f]));
			if (col === 0) b.appendChild(label('rank', r + 1));
			b.onclick = () => click(sq);
			boardEl.appendChild(b);
		}
	}
}

function label(kind, text) {
	const e = document.createElement('span');
	e.className = kind;
	e.setAttribute('aria-hidden', 'true');
	e.textContent = text;
	return e;
}

function findKing(color) {
	for (const row of game.board()) for (const p of row) if (p && p.type === 'k' && p.color === color) return p.square;
	return null;
}

function moves() {
	const h = game.history();
	movesEl.textContent = '';
	for (let i = 0; i < h.length; i += 2) {
		const li = document.createElement('li');
		li.textContent = h[i] + (h[i + 1] ? ' ' + h[i + 1] : '');
		movesEl.appendChild(li);
	}
	movesEl.parentElement.scrollTop = movesEl.parentElement.scrollHeight;
}

function status() {
	if (!ready) return 'Loading Stockfish...';
	if (game.isCheckmate()) return game.turn() === you ? 'Checkmate. Stockfish wins.' : 'Checkmate! You win!';
	if (game.isStalemate()) return 'Stalemate, a draw. No legal moves and not in check.';
	if (game.isThreefoldRepetition()) return 'A draw: the same position three times.';
	if (game.isInsufficientMaterial()) return "A draw: nobody has enough left to checkmate.";
	if (game.isDraw()) return 'A draw: fifty moves without a capture or a pawn move.';
	if (thinking) return 'Stockfish is thinking...';
	return game.inCheck() ? 'Check! Your move.' : 'Your move.';
}

function update() {
	draw();
	moves();
	statusEl.textContent = status();
	statusEl.className = 'status' + (game.isGameOver() ? ' over' : '');
}

function newGame() {
	stopEngine();
	game = new Chess();
	you = $('side').value;
	flipped = you === 'b';
	picked = null;
	engine.postMessage('ucinewgame');
	update();
	maybeEngine();
}

$('new').onclick = newGame;
$('side').onchange = () => { remember('side', $('side').value); newGame(); };
$('level').onchange = () => remember('level', $('level').value);
$('flip').onclick = () => { flipped = !flipped; update(); };
$('undo').onclick = () => {
	// back to your last turn: take back stockfish's move and yours
	stopEngine();
	picked = null;
	game.undo();
	if (game.turn() !== you) game.undo();
	update();
	maybeEngine();
};

const lv = recall('level'), sd = recall('side');
if (lv !== null && LEVELS[Number(lv)]) $('level').value = lv;
if (sd === 'w' || sd === 'b') $('side').value = sd;
you = $('side').value;
flipped = you === 'b';
update();
