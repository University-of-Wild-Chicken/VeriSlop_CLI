// Fixed SHA-256 over strict Unicode scalar UTF-8; own memory only, zero tools.
function ownViewSha256(value) {
  const size = checkpointText(value);
  checkpointNeed(Number.isSafeInteger(size.bytes), "OWN_HASH_LENGTH_NOT_SAFE");
  const constants = [
    0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
    0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
    0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
    0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
    0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
    0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
    0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
    0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
  ];
  const digest = new Uint32Array([0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,
    0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19]);
  const block = new Uint8Array(64), words = new Uint32Array(64);
  let used = 0;
  const rotate = (word, bits) => (word >>> bits) | (word << (32 - bits));
  function compress() {
    for (let i = 0; i < 16; i += 1) {
      const at = i * 4;
      words[i] = ((block[at] << 24) | (block[at+1] << 16) | (block[at+2] << 8) | block[at+3]) >>> 0;
    }
    for (let i = 16; i < 64; i += 1) {
      const x = words[i-15], y = words[i-2];
      const sigma0 = rotate(x,7) ^ rotate(x,18) ^ (x >>> 3);
      const sigma1 = rotate(y,17) ^ rotate(y,19) ^ (y >>> 10);
      words[i] = (words[i-16] + (sigma0 >>> 0) + words[i-7] + (sigma1 >>> 0)) >>> 0;
    }
    let [a,b,c,d,e,f,g,h] = digest;
    for (let i = 0; i < 64; i += 1) {
      const sigma1 = rotate(e,6) ^ rotate(e,11) ^ rotate(e,25);
      const choose = (e & f) ^ (~e & g);
      const first = (h + (sigma1 >>> 0) + (choose >>> 0) + constants[i] + words[i]) >>> 0;
      const sigma0 = rotate(a,2) ^ rotate(a,13) ^ rotate(a,22);
      const majority = (a & b) ^ (a & c) ^ (b & c);
      const second = ((sigma0 >>> 0) + (majority >>> 0)) >>> 0;
      h = g; g = f; f = e; e = (d + first) >>> 0;
      d = c; c = b; b = a; a = (first + second) >>> 0;
    }
    for (const [i, word] of [a,b,c,d,e,f,g,h].entries()) digest[i] = (digest[i] + word) >>> 0;
  }
  function append(byte) {
    block[used++] = byte;
    if (used === 64) { compress(); used = 0; }
  }
  for (const char of value) {
    const point = char.codePointAt(0);
    if (point < 0x80) append(point);
    else if (point < 0x800) { append(0xc0 | (point >>> 6)); append(0x80 | (point & 0x3f)); }
    else if (point < 0x10000) {
      append(0xe0 | (point >>> 12)); append(0x80 | ((point >>> 6) & 0x3f)); append(0x80 | (point & 0x3f));
    } else {
      append(0xf0 | (point >>> 18)); append(0x80 | ((point >>> 12) & 0x3f));
      append(0x80 | ((point >>> 6) & 0x3f)); append(0x80 | (point & 0x3f));
    }
  }
  const bits = BigInt(size.bytes) * 8n;
  checkpointNeed(bits < (1n << 64n), "OWN_HASH_LENGTH_OUTSIDE_SHA256_DOMAIN");
  append(0x80);
  while (used !== 56) append(0);
  for (let shift = 56n; shift >= 0n; shift -= 8n) append(Number((bits >> shift) & 0xffn));
  return Array.from(digest, word => word.toString(16).padStart(8,"0")).join("");
}
