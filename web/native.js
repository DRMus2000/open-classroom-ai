/* Students enter the classroom composer after native authentication. */
(() => {
  async function routeStudent() {
    try {
      if (location.pathname.startsWith('/classroom/')) return;
      const headers = {};
      const token = localStorage.getItem('token');
      if (token) headers.Authorization = 'Bearer ' + token;
      const response = await fetch('/api/classroom/v1/me', {headers});
      if (!response.ok) return;
      const me = await response.json();
      // Student quota comes from the authenticated classroom service.
      if (me.quota) location.replace('/classroom/student/');
    } catch (_) {
      // Login may still be in progress; retry without blocking it.
    } finally { setTimeout(routeStudent, 1000); }
  }
  routeStudent();
})();
