/**
 * Web CV Nguyễn Cao Thiêm - Interactive Application Logic
 * Đồng hành cùng bài giảng "Cầm lái AI" (TLU 2026)
 */

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initViewModes();
  initAtsScanner();
  initDiffSimulator();
  initProjectFilters();
  initSmoothScroll();
});

/* 1. Theme Toggle */
function initTheme() {
  const toggleBtn = document.getElementById('themeToggle');
  const savedTheme = localStorage.getItem('thiem_cv_theme') || 'dark';
  document.documentElement.setAttribute('data-theme', savedTheme);
  updateThemeIcon(savedTheme);

  if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      const currentTheme = document.documentElement.getAttribute('data-theme');
      const nextTheme = currentTheme === 'light' ? 'dark' : 'light';
      document.documentElement.setAttribute('data-theme', nextTheme);
      localStorage.setItem('thiem_cv_theme', nextTheme);
      updateThemeIcon(nextTheme);
    });
  }
}

function updateThemeIcon(theme) {
  const toggleBtn = document.getElementById('themeToggle');
  if (!toggleBtn) return;
  toggleBtn.innerHTML = theme === 'light' ? '🌙' : '☀️';
}

/* 2. View Mode Switcher (Split / New / Old) */
function initViewModes() {
  const modeButtons = document.querySelectorAll('.mode-btn');
  const splitView = document.getElementById('splitView');
  const oldCol = document.getElementById('oldCvCol');
  const newCol = document.getElementById('newCvCol');

  modeButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      modeButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const mode = btn.dataset.mode;

      if (!splitView || !oldCol || !newCol) return;

      if (mode === 'split') {
        splitView.style.gridTemplateColumns = '1fr 1fr';
        oldCol.style.display = 'flex';
        newCol.style.display = 'flex';
      } else if (mode === 'new') {
        splitView.style.gridTemplateColumns = '1fr';
        oldCol.style.display = 'none';
        newCol.style.display = 'flex';
      } else if (mode === 'old') {
        splitView.style.gridTemplateColumns = '1fr';
        oldCol.style.display = 'flex';
        newCol.style.display = 'none';
      }
    });
  });
}

/* 3. ATS & Recruiter Simulator */
function initAtsScanner() {
  const scanOldBtn = document.getElementById('scanOldCv');
  const scanNewBtn = document.getElementById('scanNewCv');
  const scoreVal = document.getElementById('atsScoreVal');
  const scoreCircle = document.getElementById('atsScoreCircle');
  const atsFeedback = document.getElementById('atsFeedback');

  if (!scanOldBtn || !scanNewBtn || !scoreVal) return;

  scanOldBtn.addEventListener('click', () => {
    scanOldBtn.classList.add('btn-primary');
    scanOldBtn.classList.remove('btn-secondary');
    scanNewBtn.classList.remove('btn-primary');
    scanNewBtn.classList.add('btn-secondary');

    animateScore(scoreVal, 62, () => {
      scoreCircle.className = 'score-circle warning';
      atsFeedback.innerHTML = `
        <div style="background: rgba(220, 38, 38, 0.1); border-left: 4px solid #dc2626; padding: 12px; border-radius: 6px; font-size: 13px;">
          <strong style="color: #ef4444;">⚠️ Đánh giá ATS & Tech Lead: 62/100 (Nguy cơ rớt vòng hồ sơ)</strong>
          <ul style="margin: 8px 0 0 18px; color: var(--text-muted);">
            <li><strong>Thiếu số đo định lượng (Metrics):</strong> Không có số liệu % tối ưu hay số lượng test (Slide 74: "Cần số đo trước-sau").</li>
            <li><strong>Nhiệm vụ chung chung:</strong> Từ ngữ "Develop bunch of feature", "Fix bugs" giống mô tả JD hơn thành tựu.</li>
            <li><strong>Chưa có năng lực AI:</strong> Không thể hiện quy trình AI-assisted, đối mặt nguy cơ bị thay thế tác vụ lặp lại (Slide 12).</li>
            <li><strong>Mục cá nhân thiếu minh chứng:</strong> Chỉ viết lời hứa "I always try my best..." (Cấm kỵ theo Slide 74).</li>
          </ul>
        </div>
      `;
    });
  });

  scanNewBtn.addEventListener('click', () => {
    scanNewBtn.classList.add('btn-primary');
    scanNewBtn.classList.remove('btn-secondary');
    scanOldBtn.classList.remove('btn-primary');
    scanOldBtn.classList.add('btn-secondary');

    animateScore(scoreVal, 96, () => {
      scoreCircle.className = 'score-circle';
      atsFeedback.innerHTML = `
        <div style="background: rgba(16, 185, 129, 0.1); border-left: 4px solid #10b981; padding: 12px; border-radius: 6px; font-size: 13px;">
          <strong style="color: #10b981;">✅ Đánh giá ATS & Tech Lead: 96/100 (Ưu tiên phỏng vấn trực tiếp!)</strong>
          <ul style="margin: 8px 0 0 18px; color: var(--text-muted);">
            <li><strong>Dòng mở đầu ấn tượng:</strong> Số đo giảm 35% RTSP latency và tăng 65% coverage tạo ấn tượng ngay 6 giây đầu.</li>
            <li><strong>Bằng chứng kiểm chứng 3 lớp:</strong> Có link live, sơ đồ kiến trúc IoT & Stream, minh chứng chịu trách nhiệm (Slide 74 & 76).</li>
            <li><strong>Năng lực Cầm lái AI:</strong> Nêu rõ AI dùng ở đâu (Gen Mock Data, Unit Test), kiểm thế nào, tiết kiệm 60% thời gian (Slide 19).</li>
            <li><strong>Hồ sơ bảo chứng:</strong> Tốt nghiệp Xuất sắc TLU (3.63), ThS VNU-UET, PM/Lead VNPT tham chiếu.</li>
          </ul>
        </div>
      `;
    });
  });
}

function animateScore(element, target, callback) {
  let start = parseInt(element.textContent) || 0;
  const duration = 600;
  const stepTime = 20;
  const steps = duration / stepTime;
  const increment = (target - start) / steps;
  let currentStep = 0;

  const timer = setInterval(() => {
    currentStep++;
    start += increment;
    element.textContent = Math.round(start);
    if (currentStep >= steps) {
      clearInterval(timer);
      element.textContent = target;
      if (callback) callback();
    }
  }, stepTime);
}

/* 4. IDE Coding Agent Diff Simulator (Slide 44-45) */
function initDiffSimulator() {
  const chk1 = document.getElementById('chk1');
  const chk2 = document.getElementById('chk2');
  const chk3 = document.getElementById('chk3');
  const btnAccept = document.getElementById('btnAcceptDiff');
  const btnReject = document.getElementById('btnRejectDiff');
  const resultBox = document.getElementById('diffResultBox');

  if (!btnAccept || !btnReject || !resultBox) return;

  btnAccept.addEventListener('click', () => {
    if (chk1.checked && chk2.checked && chk3.checked) {
      resultBox.innerHTML = `
        <div style="background: rgba(34, 197, 94, 0.15); border: 1px solid #22c55e; padding: 12px; border-radius: 6px; color: #86efac; font-size: 13px;">
          🎉 <strong>CHÍNH XÁC THEO CHUẨN SLIDE 44!</strong><br>
          Bạn đã trả lời đầy đủ 3 câu hỏi trước khi merge code của Coding Agent:
          (1) Nằm đúng phạm vi xử lý buffer RTSP; (2) Đã đọc và hiểu từng con trỏ bộ nhớ; (3) Có 3 unit test bảo vệ ca biên.
          <em>"Không merge dòng code nào chưa đọc hiểu!" (Slide 42)</em>
        </div>
      `;
    } else {
      resultBox.innerHTML = `
        <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; padding: 12px; border-radius: 6px; color: #fca5a5; font-size: 13px;">
          🛑 <strong>CẢNH BÁO VI PHẠM NGUYÊN TẮC CẦM LÁI AI!</strong><br>
          Slide 44 nhắc nhở: <em>"Trước khi chấp nhận: 3 câu hỏi phải trả lời được!"</em><br>
          Bạn chưa tick đủ 3 điều kiện kiểm chứng. Tuyệt đối không chấp nhận diff hàng loạt khi chưa đọc hiểu và chưa có test!
        </div>
      `;
    }
  });

  btnReject.addEventListener('click', () => {
    resultBox.innerHTML = `
      <div style="background: rgba(245, 158, 11, 0.15); border: 1px solid #f59e0b; padding: 12px; border-radius: 6px; color: #fcd34d; font-size: 13px;">
        ↩️ <strong>ĐÃ TỪ CHỐI DIFF (REVERT TO PREVIOUS COMMIT)</strong><br>
        Bạn đã làm đúng nguyên tắc Slide 44: Có mốc quay lại, code chưa đảm bảo an toàn bộ nhớ thì hoàn tác và yêu cầu Agent sinh lại kèm ràng buộc chặt chẽ hơn!
      </div>
    `;
  });
}

/* 5. Project Category Filters */
function initProjectFilters() {
  const filterBtns = document.querySelectorAll('.filter-btn');
  const projectCards = document.querySelectorAll('.project-card');

  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filterBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const cat = btn.dataset.filter;

      projectCards.forEach(card => {
        if (cat === 'all' || card.dataset.category.includes(cat)) {
          card.style.display = 'block';
        } else {
          card.style.display = 'none';
        }
      });
    });
  });
}

/* 6. Smooth Scroll */
function initSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
      const targetId = this.getAttribute('href');
      if (targetId === '#') return;
      const targetEl = document.querySelector(targetId);
      if (targetEl) {
        e.preventDefault();
        targetEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });
}

/* Utility Toast */
function showToast(msg) {
  const toast = document.createElement('div');
  toast.className = 'toast-alert';
  toast.textContent = msg;
  toast.style.cssText = `
    position: fixed;
    bottom: 24px;
    right: 24px;
    background: #1e293b;
    border: 1px solid #3b82f6;
    color: #fff;
    padding: 12px 20px;
    border-radius: 8px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.5);
    z-index: 9999;
    font-size: 14px;
    animation: fadeIn 0.3s;
  `;
  document.body.appendChild(toast);
  setTimeout(() => {
    toast.remove();
  }, 3000);
}
window.showToast = showToast;
