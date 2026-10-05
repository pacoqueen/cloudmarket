// Calendar view interactivity
(function() {
  'use strict';

  // Month navigation
  var navLinks = document.querySelectorAll('.calendar__arrow[data-nav]');
  navLinks.forEach(function(link) {
    link.addEventListener('click', function(e) {
      e.preventDefault();
      var url = new URL(window.location.href);
      var currentDate = url.searchParams.get('date');

      var date;
      if (currentDate) {
        date = new Date(currentDate);
      } else {
        date = new Date();
      }
      if (link.dataset.nav === 'prev') {
        date.setMonth(date.getMonth() - 1);
      } else {
        date.setMonth(date.getMonth() + 1);
      }
      url.searchParams.set('date', date.toISOString().split('T')[0]);
      window.location.href = url.toString();
    });
  });

  // Keyboard navigation for calendar
  document.addEventListener('keydown', function(e) {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
      return;
    }

    var currentUrl = new URL(window.location.href);
    var currentDate = currentUrl.searchParams.get('date');
    if (!currentDate) return;

    var date = new Date(currentDate);
    var newDate = null;

    switch(e.key) {
      case 'ArrowLeft':
        date.setDate(date.getDate() - 1);
        newDate = date;
        break;
      case 'ArrowRight':
        date.setDate(date.getDate() + 1);
        newDate = date;
        break;
      case 'ArrowUp':
        date.setDate(date.getDate() - 7);
        newDate = date;
        break;
      case 'ArrowDown':
        date.setDate(date.getDate() + 7);
        newDate = date;
        break;
      default:
        return;
    }

    e.preventDefault();
    var formatted = newDate.toISOString().split('T')[0];
    currentUrl.searchParams.set('date', formatted);
    window.location.href = currentUrl.toString();
  });
})();
