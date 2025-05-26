/**
 * @file form.js
 * @description This file contains the code that blocks the screen while htmx is working
 */

document.body.addEventListener('htmx:beforeRequest', function(evt) {
  document.body.style.opacity = 0.5;
});

document.body.addEventListener('htmx:afterRequest', function(evt) {
    document.body.style.opacity = 1.0;
});