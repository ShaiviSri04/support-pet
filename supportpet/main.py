from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django import forms
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
import random
from textblob import TextBlob  # For simple NLP
from openai import OpenAI
from datetime import datetime
import os
from dotenv import load_dotenv
from functools import lru_cache
import time

# Load environment variables from multiple possible locations
def load_api_key():
    # Try loading from environment first
    api_key = os.getenv('OPENAI_API_KEY')
    if api_key:
        return api_key
    
    # Try loading from .env in different locations
    load_dotenv()  # Try current directory
    api_key = os.getenv('OPENAI_API_KEY')
    if api_key:
        return api_key
        
    load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))  # Try supportpet directory
    api_key = os.getenv('OPENAI_API_KEY')
    if api_key:
        return api_key
    
    return None

# Load and validate API key
api_key = load_api_key()
if api_key and api_key.startswith('sk-'):
    print("API Key loaded successfully")
    openai_client = OpenAI(api_key=api_key)
else:
    print("WARNING: Invalid or missing OpenAI API key!")
    print(f"API Key format incorrect: {'Yes' if api_key and not api_key.startswith('sk-') else 'No'}")
    print(f"API Key missing: {'Yes' if not api_key else 'No'}")
    openai_client = None

# Rate limiting variables - increased limit
MAX_REQUESTS_PER_MINUTE = 10
request_timestamps = []

# Emotional response keywords dictionary
keywords = {
    'angry': [
        'I hear the anger in your voice, and it\'s completely valid to feel this way. Let\'s take a moment together to breathe deeply. Can you tell me more about what triggered this feeling?',
        'Your anger is telling us something important about your boundaries or needs. Would you like to explore what\'s underneath this emotion? We can work on healthy ways to express it.',
        'I notice you\'re feeling very angry right now. This is a strong emotion that can be overwhelming. Let\'s work on grounding techniques together. Can you tell me three things you can see in your environment?'
    ],
    'anxious': [
        'I understand how overwhelming anxiety can feel. Let\'s do a grounding exercise together: Can you name five things you can see, four you can touch, three you can hear, two you can smell, and one you can taste? Take your time with each one.',
        'Your anxiety is trying to protect you, but it might be working too hard right now. Let\'s explore what specific thoughts are running through your mind. Would you like to write them down together?',
        'I\'m here with you through this anxiety. Let\'s try a simple breathing exercise: Inhale for 4 counts, hold for 4, exhale for 4. Would you like to try this together?'
    ],
    'happy': [
        'I\'m so glad you\'re feeling happy! This is a wonderful moment to celebrate. Would you like to explore what\'s contributing to this positive feeling? It can help us understand what brings you joy.',
        'Your happiness is beautiful to witness. Let\'s capture this moment together. What specific aspects of your life are bringing you this joy?',
        'I\'m genuinely happy to see you feeling this way. This positive energy is valuable. Would you like to discuss how we can nurture and maintain these feelings?'
    ],
    'depressed': [
        'I hear the heaviness in your words, and I want you to know you don\'t have to carry this alone. Would you like to talk about what\'s been weighing on your mind?',
        'Depression can feel like a heavy cloud, but there are ways through this. Let\'s start with something small together - maybe a short walk or listening to a song you love. What feels manageable right now?',
        'I\'m here to listen without judgment. Your feelings are valid, and it\'s okay to not be okay. Would you like to explore what\'s been contributing to these feelings?'
    ],
    'sad': [
        'Your sadness is important, and I\'m here to hold space for it. Would you like to talk about what\'s bringing up these feelings?',
        'It\'s okay to feel sad, and it\'s okay to cry. These emotions are part of being human. Let\'s explore what\'s triggering this sadness together.',
        'I hear the pain in your voice. Would you like to talk about what\'s making you feel this way? We can work through this together.'
    ],
    'lonely': [
        'Loneliness can be really painful, and I want you to know you\'re not alone in feeling this way. Would you like to explore what kind of connection you\'re longing for?',
        'I hear how isolating this feels. Let\'s think together about small steps we could take to build more connection in your life. What feels manageable right now?',
        'Your need for connection is valid and important. Would you like to talk about what kind of relationships or interactions you\'re missing?'
    ],
    'overwhelmed': [
        'I understand how overwhelming this feels right now. Let\'s break this down together into smaller, more manageable pieces. What\'s the most pressing thing on your mind?',
        'It\'s okay to feel overwhelmed - this is a lot to handle. Let\'s take a moment to breathe together and then look at what needs your attention first.',
        'I hear how much you\'re carrying right now. Would you like to prioritize what needs immediate attention? We can tackle this one step at a time.'
    ],
    'grateful': [
        'I appreciate you sharing these feelings of gratitude. It\'s beautiful to see you recognizing the positive aspects of your life. Would you like to explore what\'s helping you feel this way?',
        'Your gratitude is touching to hear. Let\'s explore what\'s contributing to these feelings of appreciation. What specific aspects of your life are you grateful for?',
        'I\'m glad you\'re experiencing these feelings of gratitude. Would you like to discuss how we can nurture and maintain this positive perspective?'
    ],
    'confused': [
        'Confusion can be really unsettling. Let\'s explore your thoughts together and see if we can bring some clarity. What specific aspects are feeling unclear to you?',
        'I understand how disorienting confusion can feel. Would you like to talk through your thoughts together? Sometimes speaking them out loud can help bring clarity.',
        'It\'s okay to feel confused - this is a complex situation. Let\'s break it down together and look at what specific parts are unclear to you.'
    ],
    'excited': [
        'I\'m genuinely excited to hear about your enthusiasm! This positive energy is wonderful. Would you like to explore what\'s bringing up these feelings of excitement?',
        'Your excitement is contagious! Let\'s talk about what\'s contributing to this positive energy. What specific aspects are making you feel this way?',
        'I\'m glad you\'re feeling excited! Would you like to discuss how we can channel this energy into something meaningful?'
    ],
    'frustrated': [
        'I hear your frustration, and it\'s completely valid. Would you like to explore what\'s triggering these feelings? Sometimes understanding the source can help us find solutions.',
        'Your frustration is telling us something important. Let\'s take a moment to breathe together and then look at what\'s causing these feelings.',
        'I understand how frustrating this situation is. Would you like to talk about what specific aspects are causing this frustration?'
    ],
    'guilty': [
        'Guilt can be a heavy emotion to carry. Let\'s explore these feelings together without judgment. Would you like to talk about what\'s triggering this guilt?',
        'I hear the weight of guilt in your words. It\'s important to remember that everyone makes mistakes. Would you like to discuss what\'s making you feel this way?',
        'Your feelings of guilt are valid, but let\'s look at them with compassion. Would you like to explore what\'s contributing to these feelings?'
    ],
    'fearful': [
        'Fear can be really overwhelming, and I want you to know you\'re safe here. Would you like to talk about what\'s triggering these feelings of fear?',
        'I hear your fear, and it\'s important to acknowledge it. Let\'s explore what specific aspects are causing this anxiety together.',
        'Your fear is valid, and we can work through this together. Would you like to discuss what\'s making you feel afraid?'
    ],
    'insecure': [
        'I hear the self-doubt in your voice, and I want you to know you\'re worthy just as you are. Would you like to explore what\'s triggering these feelings of insecurity?',
        'Your feelings of insecurity are valid, but they don\'t define you. Let\'s look at your strengths together. What qualities do you value in yourself?',
        'I understand how challenging insecurity can be. Would you like to talk about what\'s contributing to these feelings? We can work on building your confidence together.'
    ],
    'bored': [
        'Boredom can sometimes mask deeper feelings or unmet needs. Would you like to explore what might be underneath this feeling of boredom?',
        'I hear that you\'re feeling bored, and it\'s interesting to explore what this might be telling us. What kind of engagement or stimulation are you longing for?',
        'Let\'s look at your boredom together - sometimes it can be a sign that we need more meaning or connection in our lives. What interests or activities usually bring you joy?'
    ],
    'stressed': [
        'Stress can feel really overwhelming, and I want you to know you don\'t have to face it alone. Would you like to talk about what\'s causing this stress?',
        'I hear the stress in your voice, and it\'s important to address it. Let\'s identify your main stressors together and work on coping strategies.',
        'Your stress is valid, and we can work on managing it together. Would you like to explore what specific aspects are causing this stress?'
    ],
    'apathetic': [
        'Apathy can be a protective response to feeling overwhelmed or disconnected. Would you like to explore what might be underneath these feelings?',
        'I hear that you\'re feeling apathetic, and it\'s important to understand why. Let\'s look at what used to bring you joy or meaning in life.',
        'Your feelings of apathy are valid, and we can work through them together. Would you like to discuss what might be contributing to this emotional state?'
    ]
}

# Suggested activities
activities = [
    "Let's take a mindful walk together - focus on each step and the sensations around you",
    "Try this breathing exercise with me: inhale for 4, hold for 4, exhale for 4",
    "Would you like to write down your thoughts in a journal? I can guide you through some prompts",
    "Let's create a calming playlist together - what songs usually help you feel better?",
    "Try some gentle stretching - I can guide you through some basic movements",
    "How about we try cooking something together? What's your favorite comfort food?",
    "Let's find a book that speaks to your current situation - what genres do you enjoy?",
    "Would you like to try some art therapy? We can start with simple drawing exercises",
    "Let's reach out to someone you trust - who comes to mind when you think of support?",
    "How about we try a puzzle together? It can help focus your mind",
    "A warm bath can be very therapeutic - would you like to try some relaxation techniques while you soak?",
    "Let's try a short meditation together - I can guide you through it",
    "A bike ride can help clear your mind - would you like to plan a route together?",
    "What's a hobby you've always wanted to try? We can explore options together",
    "Let's organize your space - sometimes creating order can help create mental clarity"
]

def check_rate_limit():
    """Check if we've exceeded our rate limit"""
    current_time = time.time()
    # Remove timestamps older than 1 minute
    global request_timestamps
    request_timestamps = [ts for ts in request_timestamps if current_time - ts <= 60]
    return len(request_timestamps) < MAX_REQUESTS_PER_MINUTE

@lru_cache(maxsize=100)
def get_cached_response(message_hash):
    """Cache for similar messages to reduce API calls"""
    return None  # Initially empty, will be populated as messages come in

def update_cache(message_hash, response):
    """Update the cache with a new response"""
    get_cached_response.cache_info()  # Just to use the lru_cache
    get_cached_response.__wrapped__.__dict__[message_hash] = response

# Models
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    email = models.EmailField()

    def __str__(self):
        return self.email

# Register UserProfile in admin
admin.site.register(UserProfile)

# Forms
class LoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)

class RegisterForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    password1 = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput)

# Views
def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            email = form.cleaned_data['email']
            password1 = form.cleaned_data['password1']
            password2 = form.cleaned_data['password2']
            
            # Check if passwords match
            if password1 != password2:
                return render(request, 'register.html', {
                    'form': form,
                    'error': 'Passwords do not match'
                })
            
            # Check if username exists
            if User.objects.filter(username=username).exists():
                return render(request, 'register.html', {
                    'form': form,
                    'error': 'Username already exists'
                })
            
            # Check if email exists
            if User.objects.filter(email=email).exists():
                return render(request, 'register.html', {
                    'form': form,
                    'error': 'Email already exists'
                })
            
            try:
                # Create user
                user = User.objects.create_user(username=username, email=email, password=password1)
                UserProfile.objects.create(user=user, email=email)
                return redirect('login')
            except Exception as e:
                return render(request, 'register.html', {
                    'form': form,
                    'error': str(e)
                })
        else:
            return render(request, 'register.html', {'form': form})
    else:
        form = RegisterForm()
        return render(request, 'register.html', {'form': form})

def user_login(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            print(f"Attempting login for email: {email}")  # Debug print
            try:
                user = User.objects.get(email=email)
                print(f"User found: {user.username}")  # Debug print
                user = authenticate(username=user.username, password=password)
                if user is not None:
                    print("Authentication successful")  # Debug print
                    login(request, user)
                    return redirect('home')
                else:
                    print("Authentication failed")  # Debug print
                    return render(request, 'login.html', {'form': form, 'error': 'Invalid password'})
            except User.DoesNotExist:
                print("User not found")  # Debug print
                return render(request, 'login.html', {'form': form, 'error': 'No account found with this email'})
        else:
            print("Form validation failed")  # Debug print
            print(form.errors)  # Debug print
    else:
        form = LoginForm()
    return render(request, 'login.html', {'form': form})

def user_logout(request):
    logout(request)
    return redirect('login')

@login_required
def home(request):
    return render(request, 'home.html')

@login_required
def about(request):
    print("About view accessed")  # Debug print
    print(f"User authenticated: {request.user.is_authenticated}")  # Debug print
    return render(request, 'about.html')

@login_required
def support(request):
    return render(request, 'support.html')

@login_required
def analyze_mood(request):
    if request.method == 'POST':
        import json
        data = json.loads(request.body)
        user_input = user_input = data.get('user_input', '').lower()
        analysis = TextBlob(user_input)

        # Check for keywords in user input
        matched_emotions = []
        for emotion in keywords.keys():
            if emotion in user_input:
                matched_emotions.append(emotion)

        if matched_emotions:
            # Randomly select one of the matched emotions
            emotion = random.choice(matched_emotions)
            # Get all suggestions for the emotion
            suggestions = keywords[emotion]
            # Randomly select one suggestion
            suggestion = random.choice(suggestions)
        else:
            # If no emotions matched, use sentiment analysis
            sentiment = analysis.sentiment.polarity
            if sentiment > 0.3:
                suggestion = random.choice(keywords['happy'])
            elif sentiment < -0.3:
                suggestion = random.choice(keywords['sad'])
            else:
                suggestion = "I'm here to listen and support you. Would you like to share more about how you're feeling?"

        # Select a random activity
        activity = random.choice(activities)

        return JsonResponse({
            'suggestion': suggestion,
            'activity': activity
        })

    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def chat(request):
    if request.method == 'GET':
        return render(request, 'chat.html', {'current_time': datetime.now().strftime('%I:%M %p')})
    
    elif request.method == 'POST':
        try:
            # Parse JSON data from request body
            import json
            data = json.loads(request.body)
            user_message = data.get('message', '').strip()
            
            if not user_message:
                return JsonResponse({'error': 'No message provided'}, status=400)
            
            print(f"Received message: {user_message}")  # Debug print
            
            # Check cache first
            message_hash = hash(user_message.lower())
            cached_response = get_cached_response(message_hash)
            if cached_response:
                print("Using cached response")
                return JsonResponse({'response': cached_response})
            
            # Try OpenAI if client is available and within rate limit
            if openai_client and check_rate_limit():
                try:
                    print("Attempting OpenAI request...")  # Debug print
                    
                    # Optimize the system message to be more concise
                    system_message = """You are PetComfy, an empathetic support companion. Be warm, professional, and focused on emotional support. Validate feelings, offer coping strategies, and ask open-ended questions. Keep responses concise."""
                    
                    messages = [
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": user_message}
                    ]
                    
                    request_timestamps.append(time.time())  # Record request time
                    
                    response = openai_client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=messages,
                        max_tokens=150,
                        temperature=0.7,
                        presence_penalty=0.6,
                        frequency_penalty=0.5
                    )
                    
                    bot_response = response.choices[0].message.content
                    print("OpenAI request successful")
                    
                    # Cache the response
                    update_cache(message_hash, bot_response)
                    return JsonResponse({'response': bot_response})
                    
                except Exception as e:
                    print(f"OpenAI API error: {str(e)}")
                    # Fall through to mood analysis
            else:
                print("OpenAI client not available or rate limited")
            
            # Fall back to mood analysis
            print("Using mood analysis fallback")
            analysis = TextBlob(user_message.lower())
            
            # Use the analyze_mood logic
            matched_emotions = []
            for emotion in keywords.keys():
                if emotion in user_message.lower():
                    matched_emotions.append(emotion)

            if matched_emotions:
                emotion = random.choice(matched_emotions)
                suggestion = random.choice(keywords[emotion])
            else:
                sentiment = analysis.sentiment.polarity
                if sentiment > 0.3:
                    suggestion = random.choice(keywords['happy'])
                elif sentiment < -0.3:
                    suggestion = random.choice(keywords['sad'])
                else:
                    suggestion = "I'm here to listen and support you. Would you like to share more about how you're feeling?"

            activity = random.choice(activities)
            response_text = f"{suggestion}\n\nHere's an activity we could try: {activity}"
            
            # Cache the fallback response too
            update_cache(message_hash, response_text)
            return JsonResponse({'response': response_text})
            
        except json.JSONDecodeError as e:
            print(f"JSON Decode Error: {str(e)}")
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            print(f"General Error in chat: {str(e)}")
            print(f"Error type: {type(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return JsonResponse({'error': str(e)}, status=500)

# URLs
urlpatterns = [
    path('register/', register, name='register'),
    path('login/', user_login, name='login'),
    path('logout/', user_logout, name='logout'),
    path('home/', home, name='home'),
    path('about/', about, name='about'),
    path('support/', support, name='support'),
    path('chat/', chat, name='chat'),
    path('analyze_mood/', analyze_mood, name='analyze_mood'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
