// just let me paste
// run this from the console on whatever website is giving you a hassle.
document.querySelectorAll('input, textarea').forEach(el => {
  el.onpaste = null;
  el.oncopy = null;
  el.oncut = null;
  el.onkeydown = null;
  el.oninput = null;

  // Block any event listeners added via addEventListener
  ['paste', 'copy', 'cut', 'keydown', 'input'].forEach(event => {
    el.addEventListener(event, e => e.stopImmediatePropagation(), true);
  });
});
