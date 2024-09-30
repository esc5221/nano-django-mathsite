# /// script
# dependencies = [
#     "nanodjango@git+https://github.com/esc5221/nanodjango",
#     "Pillow",
# ]
# ///


import os
from nanodjango import Django

# 도메인 설정
domain = os.environ.get("APP_DOMAIN", "domain.com")
print("domain:", domain)

# nanodjango 인스턴스 설정
app = Django(
    ADMIN_URL="secret-admin/",
    ALLOWED_HOSTS=["localhost", "127.0.0.1", "0.0.0.0", domain],
    CSRF_TRUSTED_ORIGINS=[f"https://{domain}"],
    SECRET_KEY=os.environ.get("SECRET_KEY", "unset"),
    SQLITE_DATABASE="mathsite.sqlite3",
    MIGRATIONS_DIR="mathsite_migrations",
    EXTRA_APPS=[],
)

"""
"""

from django.db import models
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.urls import include
from django.views.generic import ListView
from django.http import HttpResponse
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django import forms


User = get_user_model()

"""
models.py
"""


@app.admin
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    image = models.ImageField(default="default.jpg", upload_to="profile_pics")

    def __str__(self):
        return f"{app.user.username}의 프로필"


# 문제 모델
@app.admin
class Problem(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    answer = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    hint = models.TextField(blank=True, null=True)

    def __str__(self):
        return app.title


# 푼 문제 모델
@app.admin
class SolvedProblem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE)
    solved_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{app.user.username} - {app.problem.title}"


"""
signals.py
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_profile(sender, instance, **kwargs):
    try:
        instance.userprofile.save()
    except:
        pass


"""
views.py
"""


# 인덱스 뷰
@app.route("/", name="home")
def index(request):
    return render(request, "index.html")


# 사용자 가입 폼 커스터마이징 (유저 이름과 비밀번호만 받도록 설정)
from django import forms
from django.contrib.auth.forms import UserCreationForm


class CustomUserCreationForm(UserCreationForm):
    image = forms.ImageField(
        required=False, widget=forms.FileInput(attrs={"class": "form-control"})
    )

    class Meta:
        model = User
        fields = ("username", "email", "image", "password1", "password2")


@app.route("/signup/", name="signup")
def signup_view(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # 사용자 인증 및 로그인
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password1")
            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                return redirect("/problems/")
    else:
        form = CustomUserCreationForm()
    return render(request, "signup.html", {"form": form})


# 로그인 뷰
@app.route("/login/", name="login")
def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect("/problems/")
        else:
            return render(request, "login.html", {"error": "Invalid credentials"})
    return render(request, "login.html")


# 로그아웃 뷰
@app.route("/logout/", name="logout")
def logout_view(request):
    logout(request)
    return redirect("/login/")


# ---


# 문제 목록 뷰
@app.route("/problems/", name="problem_list")
def problem_list(request):
    if not request.user.is_authenticated:
        return redirect("/login/")
    problems = Problem.objects.all()
    return render(request, "problem_list.html", {"problems": problems})


# 문제 상세 뷰
@app.route("/problems/<int:problem_id>/", name="problem_detail")
def problem_detail(request, problem_id):
    if not request.user.is_authenticated:
        return redirect("/login/")
    try:
        problem = Problem.objects.get(id=problem_id)
    except Problem.DoesNotExist:
        return HttpResponse("문제가 존재하지 않습니다.", status=404)

    solved = SolvedProblem.objects.filter(user=request.user, problem=problem).exists()
    correct = None
    if request.method == "POST" and not solved:
        user_answer = request.POST.get("answer")
        # 정답을 리스트로 분리하여 여러 정답을 허용
        correct_answers = [ans.strip().lower() for ans in problem.answer.split(",")]
        user_answer_clean = user_answer.strip().lower()
        if user_answer_clean in correct_answers:
            SolvedProblem.objects.create(user=request.user, problem=problem)
            solved = True
            correct = True
        else:
            correct = False
    return render(
        request,
        "problem_detail.html",
        {"problem": problem, "solved": solved, "correct": correct},
    )


# 푼 문제 목록 뷰
@app.route("/solved/", name="solved_list")
def solved_list(request):
    if not request.user.is_authenticated:
        return redirect("/login/")
    solved_problems = SolvedProblem.objects.filter(user=request.user).select_related(
        "problem"
    )
    return render(request, "solved_list.html", {"solved_problems": solved_problems})


# 대시보드 뷰
@app.route("/dashboard/", name="dashboard")
def dashboard(request):
    if not request.user.is_authenticated:
        return redirect("/login/")
    total_solved = SolvedProblem.objects.filter(user=request.user).count()
    total_problems = Problem.objects.count()
    percentage = (total_solved / total_problems * 100) if total_problems > 0 else 0
    return render(
        request,
        "dashboard.html",
        {
            "total_solved": total_solved,
            "total_problems": total_problems,
            "percentage": percentage,
        },
    )


# 프로필 뷰
@app.route("/profile/", name="profile")
def profile(request):
    if not request.user.is_authenticated:
        return redirect("/login/")
    solved_problems = SolvedProblem.objects.filter(user=request.user).select_related(
        "problem"
    )
    return render(request, "profile.html", {"solved_problems": solved_problems})


# ---


def create_root_user():
    if User.objects.filter(username="root").exists():
        return
    User.objects.create_superuser("root", password="123123")


def create_initial_problems():
    existing_problems = Problem.objects.count()
    if existing_problems < 10:
        # 다양한 난이도의 문제 목록
        math_problems = [
            {
                "title": "1차 방정식 풀기",
                "description": "다음 1차 방정식을 풀어 \( x \)의 값을 구하세요: \( 2x + 5 = 13 \)",
                "answer": "4",
                "hint": "양변에서 5를 빼고, 2로 나누세요.",
            },
            {
                "title": "이차 방정식의 해 구하기",
                "description": "다음 이차 방정식을 풀어 한 가지 해를 구하세요: \( x^2 - 5x + 6 = 0 \)",
                "answer": "3",
                "hint": "인수분해를 시도해 보세요.",
            },
            {
                "title": "삼각형의 넓이 계산",
                "description": "밑변이 \( 10 \)cm이고 높이가 \( 5 \)cm인 삼각형의 넓이를 구하세요.",
                "answer": "25 cm²",
                "hint": "넓이 공식은 밑변 × 높이 ÷ 2입니다.",
            },
            {
                "title": "원둘레 계산",
                "description": "반지름이 \( 7 \)cm인 원의 둘레를 구하세요. \( \pi \approx 3.14 \)를 사용하세요.",
                "answer": "43.96 cm",
                "hint": "원둘레 공식은 \( 2 \pi r \)입니다.",
            },
            {
                "title": "퍼센트 증가율",
                "description": "어떤 물건의 가격이 \( 20,000 \)원에서 \( 25,000 \)원으로 올랐을 때, 퍼센트 증가율을 구하세요.",
                "answer": "25%",
                "hint": "증가분을 원래 값으로 나누고 100을 곱하세요.",
            },
            {
                "title": "평균 계산",
                "description": "학생들의 수학 점수가 \( 85, 90, 78, 92, 88 \)일 때, 평균 점수를 구하세요.",
                "answer": "86.6",
                "hint": "모든 점수의 합을 학생 수로 나누세요.",
            },
            {
                "title": "지수 계산",
                "description": "2의 5제곱을 계산하세요.",
                "answer": "32",
                "hint": "2를 5번 곱하세요.",
            },
            {
                "title": "소인수분해",
                "description": "다음 숫자를 소인수분해하세요: 60",
                "answer": "2^2 * 3 * 5",
                "hint": "가장 작은 소수부터 나눠보세요.",
            },
            {
                "title": "수열 문제",
                "description": "다음 수열에서 \( 7 \)번째 숫자를 구하세요: \( 2, 4, 6, 8, 10, 12, \dots \)",
                "answer": "14",
                "hint": "각 항은 2씩 증가합니다.",
            },
            {
                "title": "미적분 문제",
                "description": "다음 함수를 미분하세요: \( f(x) = x^3 - 2x^2 + x \)",
                "answer": "3x^2 - 4x + 1",
                "hint": "각 항의 차수를 줄이세요.",
            },
        ]

        for problem_data in math_problems:
            if Problem.objects.filter(title=problem_data["title"]).exists():
                continue  # 중복된 문제는 건너뜀
            Problem.objects.create(
                title=problem_data["title"],
                description=problem_data["description"],
                answer=problem_data["answer"],
                hint=problem_data["hint"],
            )
        print("초기 수학 문제가 데이터베이스에 추가되었습니다.")


# ---


if __name__ == "__main__":
    from nanodjango.app import exec_manage

    app._prepare(is_prod=False)
    exec_manage("makemigrations", app.app_name)
    exec_manage("migrate")

    create_root_user()
    create_initial_problems()

    app.run()
