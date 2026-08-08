let currentPage = 'page-home';
let selectedRole = null;

function goToPage(pageId) {
  const current = document.getElementById(currentPage);
  const next = document.getElementById(pageId);
  if (!current || !next) return;

  current.classList.remove('active');
  current.classList.add('exit');

  setTimeout(() => {
    current.classList.remove('exit');
    next.classList.add('active');
    currentPage = pageId;
  }, 300);
}

function selectRole(role) {
  selectedRole = role;
  document.querySelectorAll('.role-card').forEach(c => c.classList.remove('selected'));
  const targetCard = document.getElementById('role-' + role);
  if (targetCard) {
    targetCard.classList.add('selected');
  }
}

function createRipple(e, btn) {
  const ripple = document.createElement('span');
  ripple.className = 'ripple';
  const rect = btn.getBoundingClientRect();
  const size = Math.max(rect.width, rect.height);
  ripple.style.width = ripple.style.height = size + 'px';
  ripple.style.left = (e.clientX - rect.left - size / 2) + 'px';
  ripple.style.top = (e.clientY - rect.top - size / 2) + 'px';
  btn.appendChild(ripple);

  setTimeout(() => ripple.remove(), 600);
}

function showToast(msg) {
  const toast = document.getElementById('toast');
  if (!toast) return;

  toast.textContent = msg;
  toast.style.opacity = '1';
  toast.style.transform = 'translateX(-50%) translateY(0)';

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(-50%) translateY(100px)';
  }, 2500);
}

function handleLogin() {
  const email = document.getElementById('login-email').value;
  const password = document.getElementById('login-password').value;

  if (!email || !password) {
    const btn = document.querySelector('#page-login .mj-btn-primary');
    if (btn) {
      btn.classList.add('shake');
      setTimeout(() => btn.classList.remove('shake'), 500);
    }
    showToast('Please fill in all fields');
    return;
  }

  showToast('Logging in...');
  setTimeout(() => goToPage('page-success'), 1200);
}

function handleSignup() {
  const fname = document.getElementById('signup-fname').value;
  const lname = document.getElementById('signup-lname').value;
  const email = document.getElementById('signup-email').value;
  const phone = document.getElementById('signup-phone').value;
  const password = document.getElementById('signup-password').value;
  const confirm = document.getElementById('signup-confirm').value;
  const terms = document.getElementById('terms').checked;

  if (!fname || !lname || !email || !phone || !password) {
    const btn = document.querySelector('#page-signup-form .mj-btn-primary');
    if (btn) {
      btn.classList.add('shake');
      setTimeout(() => btn.classList.remove('shake'), 500);
    }
    showToast('Please fill in all fields');
    return;
  }

  if (password !== confirm) {
    showToast('Passwords do not match');
    return;
  }

  if (!terms) {
    showToast('Please accept the terms');
    return;
  }

  showToast('Creating your account...');
  setTimeout(() => goToPage('page-success'), 1500);
}