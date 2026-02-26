// ==========================================
// RUN AFTER PAGE LOAD
// ==========================================
document.addEventListener("DOMContentLoaded", function () {

    // ===============================
    // LIVE PREVIEW FUNCTION
    // ===============================
    function bindLivePreview(inputId, previewId, defaultText) {
        const input = document.getElementById(inputId);
        const preview = document.getElementById(previewId);

        if (!input || !preview) return;

        input.addEventListener("input", function () {
            preview.innerText = this.value || defaultText;
        });
    }

    // PERSONAL LIVE PREVIEW
    bindLivePreview("full_name", "preview_name", "Your Name");
    bindLivePreview("job_title", "preview_title", "Your Job Title");
    bindLivePreview("email", "preview_email", "Email");
    bindLivePreview("phone", "preview_phone", "Phone");
    bindLivePreview("objective", "preview_summary", "Your summary here...");

    // ===============================
    // SKILLS LIVE PREVIEW
    // ===============================
    const skillsInput = document.querySelector('input[name="skills"]');
    const skillsPreview = document.getElementById("preview_skills");

    if (skillsInput && skillsPreview) {
        skillsInput.addEventListener("input", function () {
            const skills = this.value.trim().split(/\s+/);

            skillsPreview.innerHTML = skills.map(skill =>
                `<span>${skill}</span>`
            ).join(" ");
        });
    }

    // ===============================
    // EDUCATION SECTION
    // ===============================
    let educationCount = document.querySelectorAll(".education-block").length;
    if (educationCount === 0) educationCount = 1;

    window.addEducation = function () {

        educationCount++;

        const container = document.getElementById("education-container");
        if (!container) return;

        const block = document.createElement("div");
        block.className = "education-block";

        block.innerHTML = `
            <input type="text" name="degree_${educationCount}" placeholder="Degree">
            <input type="text" name="university_${educationCount}" placeholder="University">
            <input type="text" name="year_${educationCount}" placeholder="Year of Passing">
            <input type="text" name="percentage_${educationCount}" placeholder="Percentage / CGPA">
        `;

        container.appendChild(block);
    };

    // ===============================
    // FORM AUTO REFRESH PREVIEW
    // ===============================
    const form = document.querySelector("form");

    if (form) {
        form.addEventListener("submit", function () {
            setTimeout(() => {
                const iframe = document.getElementById("livePreview");
                if (iframe) iframe.src = iframe.src;
            }, 800);
        });
    }

});


// ==========================================
// GITHUB LIVE PREVIEW
// ==========================================
const githubInput = document.querySelector('input[name="github_1"]');
const githubPreview = document.getElementById("preview_github");

if (githubInput && githubPreview) {
    githubInput.addEventListener("input", function () {
        if (this.value.trim() !== "") {
            githubPreview.innerHTML =
                `<a href="${this.value}" target="_blank" style="color:green;font-weight:bold;">
                    View on GitHub
                </a>`;
        } else {
            githubPreview.innerHTML = "";
        }
    });
}


// ==========================================
// AI SUMMARY GENERATOR
// ==========================================
function generateAI() {

    let roleInput = document.querySelector('input[name="job_title"]');
    let role = roleInput ? roleInput.value : "";

    let experience = document.getElementById("experience_level")?.value || "";
    let skills = document.getElementById("ai_skills")?.value || "";

    if (!role) {
        alert("Please enter Job Title first");
        return;
    }

    fetch("/generate-summary", {
        method: "POST",
        headers: {
            "Content-Type": "application/x-www-form-urlencoded"
        },
        body:
            "role=" + encodeURIComponent(role) +
            "&experience=" + encodeURIComponent(experience) +
            "&skills=" + encodeURIComponent(skills)
    })
    .then(res => res.json())
    .then(data => {
        const summaryBox = document.getElementById("objective");
        if (summaryBox) summaryBox.value = data.summary;
    });
}


// ==========================================
// RESUME SCORE ANALYZER
// ==========================================
function analyzeResume() {

    const resumeId = document.getElementById("resume_id").value;

    fetch("/analyze-resume", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            resume_id: resumeId
        })
    })
    .then(res => res.json())
    .then(data => {

        const box = document.getElementById("scoreBox");
        const bar = document.getElementById("scoreBar");
        const text = document.getElementById("scoreText");
        const list = document.getElementById("feedbackList");

        box.style.display = "block";
        bar.style.width = data.score + "%";
        text.innerText = "Score: " + data.score + "/100";

        list.innerHTML = "";

        if (data.feedback.length === 0) {
            list.innerHTML = "<li>Excellent Resume!</li>";
        } else {
            data.feedback.forEach(f => {
                list.innerHTML += "<li>" + f + "</li>";
            });
        }
    });
}