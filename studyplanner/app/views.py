from django.shortcuts import render
from django.http import HttpResponse
from django.template import loader
from django.shortcuts import redirect
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.middleware import csrf
from django.shortcuts import redirect
from django.core.files.storage import default_storage
import uuid
from studyplanner.settings import *
import json
from datetime import datetime

# Create your views here.
from .models import *
from datetime import date,timedelta

navigation_list = [
    {'icon': 'img/icon_deadlines.png', 'title': 'Deadlines', 'url': '/deadlines'},
    {'icon': 'img/icon_modules.png', 'title': 'Modules', 'url': '/modules'},
    {'icon': 'img/icon_gantt.png', 'title': 'Gantt Chart', 'url': '/ganttchart'},
    {'icon': 'img/icon_add.png', 'title': 'Add Task', 'url': '/createTask'},
    {'icon': 'img/icon_logout.png', 'title': 'Logout', 'url': '/logout'}
]

def isLoggedIn(request):
    if 'userid' in request.COOKIES:
        return True
    return False

def isValidEmail(email):
    try:
        validate_email(email)
        return True
    except ValidationError:
        return False

def isValidPassword(password):
    return len(password) > 7

def getUser(request):
    return User.objects.get(userid=request.COOKIES['userid'])

def loginUser(response, userid):
    response.set_cookie('userid', userid)

def index(request):
    user_list = User.objects.all()
    context = {
        'user_list': user_list
    }
    return render(request, 'index.html', context)

def createTask(request, id=None):
    if not isLoggedIn(request):
        return redirect('/')

    userid = request.COOKIES['userid']
    user = getUser(request)

    modules = Module.objects.filter(semester=user.activeSemester)

    jsonModules = {}
    for module in modules:
        jsonModules[module.code] = {}
        jsonModules[module.code]['name'] = module.name
        jsonModules[module.code]['description']= module.description
        jsonModules[module.code]['assessments'] = []
        assessments = Assessment.objects.filter(module=module)
        for assessment in assessments:
            jsonAssessment = {}
            jsonAssessment['id'] = str(assessment.uid)
            jsonAssessment['name'] = assessment.name
            jsonAssessment['description'] = assessment.description
            jsonAssessment['weight'] = assessment.weight
            jsonAssessment['startDate'] = str(assessment.startDate)
            jsonAssessment['deadline'] = str(assessment.deadline)
            jsonAssessment['assessmentType'] = assessment.type_a
            jsonAssessment['tasks'] = []
            tasks = StudyTask.objects.filter(assessment = assessment)
            for task in tasks:
                jsonTask = {}
                jsonTask['id'] = str(task.uid)
                jsonTask['name'] = task.name
                jsonTask['description'] = task.description
                jsonTask['duration'] = str(task.duration)
                jsonTask['dependencies'] = []
                for dependency in task.requiredTasks.all():
                    jsonTask['dependencies'].append(str(dependency.uid))
                jsonAssessment['tasks'].append(jsonTask)
            jsonModules[module.code]['assessments'].append(jsonAssessment)
    
    jsonPredefined = {'modulecode':'none','assessmentid':'none'}
    if id!=None:
        try:
            uuid.UUID(id)
        except:
            return render(request, 'badrequest.html', _badRequestContext(request,"The page does not exist."))
        try:
            assessment=Assessment.objects.get(pk=id)
        except Assessment.DoesNotExist:
            return render(request, 'badrequest.html', _badRequestContext(request,"The page does not exist."))
        if assessment.module.semester.user != user:
            return render(request, 'badrequest.html', _badRequestContext(request,"You don't have permission to view this page."))
        jsonPredefined = {'modulecode':assessment.module.code,'assessmentid':str(assessment.uid)}


    context = {
        'navigation': navigation_list,
        'active': 'Add Task',
        'semesters': _getAllSemesters(request),
        'user': getUser(request),
        'modelData': json.dumps(jsonModules),
        'predefinedData':json.dumps(jsonPredefined),
    }
    return render(request, 'createTask.html', context)

def processTask(request):
    assessmentid = request.POST['assessment']
    name = request.POST['name']
    desc = request.POST['description']
    duration = timedelta(days=int(request.POST['duration']))
   
    task = StudyTask(name=name, description=desc, duration=duration, assessment=Assessment.objects.get(uid=assessmentid))
    task.save()
    return redirect('/task/' + str(task.uid) + '/')

def login(request):
    # If user already logged in
    if isLoggedIn(request):
        return redirect('/dashboard')
    
    # error context
    context = {}
    if 'error' in request.GET:
        context['error'] = request.GET['error']

    return render(request,'login.html', context)

def processLogin(request):
    email = request.POST['email']
    if not isValidEmail(email):
        print('Invalid email.')
        return redirect('/error=Invalid Email')
    
    user = User.objects.filter(email=email)

    if len(user) == 0:
        print('User does not exist.')
        return redirect('/?error=User does not exist.')

    user = user[0]

    password = request.POST['password']
    
    if user.password != password:
        print('Wrong password!')
        return redirect('/?error=Wrong password.')

    # User login should be verified now
    print('Login success!')

    # Set logged in cookie
    response = redirect('/')
    loginUser(response, user.userid)

    return response

def createAccount(request):
    if isLoggedIn(request):
        return redirect('/dashboard')
    context = {}
    if 'error' in request.GET:
        context['error'] = request.GET['error']
    return render(request, 'createaccount.html', context)

def processAccount(request):
    post = request.POST
    response = redirect('/')
    if post['action'] == 'createaccount':
        email = post['email']
        if not isValidEmail(email):
            return redirect('/createaccount?error=Invalid email')

        fname = post['fname']
        lname = post['lname']
        if len(fname) == 0 or len(lname) == 0:
            return redirect('/createaccount?error=Names must not be empty')

        password = post['password']
        if not isValidPassword(password):
            return redirect('/createaccount?error=Password must be at least 8 characters long')
        
        # User data is valid so create account
        user = User(email=email, firstname=fname, lastname=lname, password=password)
        response = redirect('/')
        try:
            user.save()
            loginUser(response, user.userid)
        except Exception as e:
            return redirect('/createaccount?error=' + str(e))

    return response

def logout(request):
    response = redirect('/')
    response.delete_cookie('userid')
    return response

def dashboard(request):
    if not isLoggedIn(request):
        return redirect('/')
    context = {
        'navigation': navigation_list,
        'active': '',
        'user': getUser(request),
        'semesters': _getAllSemesters(request),
        'csrf': csrf.get_token(request),
        'disable_nav': True
    }
    if len(SemesterStudyProfile.objects.filter(user=getUser(request))) == 0:
        return render(request, 'uploadssp.html', context)
    else:
        return redirect('/deadlines')

def _createSemesterStudyProfile(request, content, userid):
    user = getUser(request)

    profile = SemesterStudyProfile(year=content['Year'], semester=content['Semester'], user=user)
    profile.save()
    # Add modules to study profile
    for m in content['Modules']:
        module = Module(name=m['Name'], code=m['Code'], description=m['Description'], semester=profile)
        module.save()
        # Add assessments to modules
        for a in m['Assessments']:
            assessmentType = 'CW' if a['Type'] == 'cw' else 'EX'
            if assessmentType == 'CW':    
                startdate = datetime.strptime(a['startdate'], DTFORMAT).date()
                enddate = datetime.strptime(a['enddate'], DTFORMAT).date()
                name = module.name + ' Coursework (due ' + enddate.strftime("%B") + ')'
                assessment = Assessment(name=name,weight=a['weight'], startDate=startdate, deadline=enddate, type_a=assessmentType, module=module)
            else:
                date = datetime.strptime(a['date'], DTFORMAT).date()
                name = module.name + ' Exam'
                assessment = Assessment(name=name,weight=a['weight'], startDate=date, deadline=date, type_a=assessmentType, module=module)
            assessment.save()
    user.activeSemester = profile
    user.save()
            
def uploadHubFile(request):
    # If user is not logged in, redirect to login page
    if not isLoggedIn(request):
        return redirect('/')
    
    userid = request.COOKIES['userid']
    if request.method == 'POST':
        file = request.FILES['hubfile']
        contentString = file.read()
        contentJSON = json.loads(contentString)
        _createSemesterStudyProfile(request, contentJSON, userid)

    return redirect('/dashboard')
    
def uploadDisplayPic(request):
    # If user is not logged in, redirect to login page
    if not isLoggedIn(request):
        return redirect('/')
    userid = request.COOKIES['userid']
    if request.method == 'POST':
        file = request.FILES['displaypic']
        filename = default_storage.save('app/static/img/user/' + file.name, file)
        u = getUser(request)
        u.displaypic = file.name
        u.save()
        print(filename)

    return redirect('/dashboard')
    

def _getAllSemesters(request):
    userid = request.COOKIES['userid']
    user = getUser(request)
    allSemesters = user.semesterstudyprofile_set.all()
    current = user.activeSemester
    if current is None:
        return {'current': None, 'semesters': []}
    to_exclude = SemesterStudyProfile.objects.filter(uid=current.uid)
    semester_options = allSemesters.difference(to_exclude)
    semesters_list = list()
    for sem in semester_options:
        item = {'name':sem.semester,'id':sem.uid}
        semesters_list.append(item)
    semesters = {'current':current.semester,'semesters':semesters_list}
    return semesters


def deadlines(request):
    if not isLoggedIn(request):
        return redirect('/')
    today = date.today()
    userid = request.COOKIES['userid']
    u = getUser(request)
    #u = User.objects.all()[0]
    s = u.activeSemester
    deadlines = s.allAssessments().order_by('deadline')
    upcoming = list()
    inprogress = list()
    missed = list()
    completed = list()
    for dl in deadlines:
        deadline = dl.deadline
        progress = dl.progress()
        p = int(progress*100)
        diff_date = deadline - today
        diff_days = diff_date.days
        if diff_days > 7:
            weeks = int(diff_days/7)
            dur = str(weeks) + ' w'
            days = diff_days - weeks*7
            if days>0:
                dur = dur + ' ' + str(days) + ' d'
        else:
            dur = str(diff_days) + ' d'
        item = {'name':dl.name,'date':deadline,'progress':p,'id':dl.uid,'duration':dur}

        # Deadline has passed and has not been completed yet -> missed
        if deadline < today and progress<1.0:
            missed.append(item)
        # Progress is 100% -> completed
        if progress==1.0:
            completed.append(item)
        # Progress is more than 0%, but less than 100% -> in progress
        if progress>0.0 and progress<1.0:
            inprogress.append(item)
        # Deadline hasn't passed yet -> upcoming
        if not(deadline < today):
            # If deadline is in less than a month it will always be added to upcoming
            # If it is further away, it will be added is there are less than 4 deadlines
            # so far on the list (to avoid overwhelming)
            if diff_days<31 or len(upcoming)<4:
                upcoming.append(item)
    completed.reverse() #showing the most recent completed first
    context = {
        'navigation': navigation_list,
        'active': 'Deadlines',
        'user': getUser(request),
        'semesters': _getAllSemesters(request),
        'upcoming' : upcoming,
        'inprogress' : inprogress,
        'missed' : missed,
        'completed' : completed
    }
    return render(request, 'deadlines.html', context)

def assessment(request, id=None):
    if not isLoggedIn(request):
        return redirect('/')
    userid = request.COOKIES['userid']
    user = getUser(request)
    try:
        uuid.UUID(id)
    except:
        return render(request, 'badrequest.html', _badRequestContext(request,"The page does not exist."))
    try:
        assessment=Assessment.objects.get(pk=id)
    except Assessment.DoesNotExist:
        return render(request, 'badrequest.html', _badRequestContext(request,"The page does not exist."))
    if assessment.module.semester.user != user:
        return render(request, 'badrequest.html', _badRequestContext(request,"You don't have permission to view this page."))
    tasks = list()
    milestones = list()
    for t in assessment.studytask_set.all():
        p = int(t.progress()*100)
        item = {'name' : t.name, 'progress' : p, 'id' : t.uid }
        tasks.append(item)
    for m in Milestone.objects.filter(assessment=assessment):
        status_img = "img/icon_cross.png"
        if(m.hasBeenReached()):
            status_img = "img/icon_check.png"
        item = {'name' : m.name, 'status' : status_img, 'id' : m.uid }
        milestones.append(item)
    progress = int(assessment.progress()*100)
    assessment_info = {
        'uid' : assessment.uid,
        'name' : assessment.name,
        'type' : assessment.get_type_a_display(),
        'module' : assessment.module.name,
        'module_id' : assessment.module.uid,
        'startdate' : assessment.startDate,
        'deadline' : assessment.deadline,
        'weight' : assessment.weight,
        'description' : assessment.description,
        'progress' : progress,
        'tasks' : tasks,
        'milestones' : milestones
    }
    context = {
        'navigation': navigation_list,
        'active': 'Deadlines',
        'user': getUser(request),
        'semesters': _getAllSemesters(request),
        'assessment' : assessment_info
    }
    return render(request, 'assessment.html', context)

def task(request, id=None):
    if not isLoggedIn(request):
        return redirect('/')
    userid = request.COOKIES['userid']
    user = getUser(request)
    try:
        uuid.UUID(id)
    except:
        return render(request, 'badrequest.html', _badRequestContext(request,"The page does not exist."))
    try:
        task=StudyTask.objects.get(pk=id)
    except StudyTask.DoesNotExist:
        return render(request, 'badrequest.html', _badRequestContext(request,"The page does not exist."))
    if task.assessment.module.semester.user != user:
        return render(request, 'badrequest.html', _badRequestContext(request,"You don't have permission to view this page."))
    activities = list()
    notes = list()
    requiredTasks = list()
    required_options = list()
    for a in task.studyactivity_set.all():
        p = int(a.progress()*100)
        item = {'name' : a.name, 'type' : a.get_type_act_display(),
            'progress' : p, 'id' : a.uid
        }
        activities.append(item)
    for n in task.note_set.all():
        item = {'note' : n.notes, 'date' : n.date, 'id' : n.uid }
        notes.append(item)
    for t in task.requiredTasks.all():
        item = {'name' : t.name, 'id' : t.uid }
        requiredTasks.append(item)
    alltasks = task.assessment.studytask_set.all()
    t1 = task.requiredTasks.all()
    t2 = StudyTask.objects.filter(uid=id)
    task_options = alltasks.difference(t1,t2)
    for o in task_options:
        item = {'name' : o.name, 'id' : o.uid }
        required_options.append(item)
    progress = int(task.progress()*100)
    task_info = {
        'uid' : task.uid,
        'name' : task.name,
        'assessment' : task.assessment,
        'assessment_id' : task.assessment.uid,
        'duration' : task.duration.days,
        'description' : task.description,
        'progress' : progress,
        'activities' : activities,
        'notes' : notes,
        'tasks' : requiredTasks,
        'options' : required_options,
        'act_type_options' : StudyActivity.getActTypes(),
    }
    context = {
        'navigation': navigation_list,
        'active': 'Deadlines',
        'user': getUser(request),
        'semesters': _getAllSemesters(request),
        'task' : task_info
    }
    return render(request, 'task.html', context)

def activity(request, id=None):
    if not isLoggedIn(request):
        return redirect('/')
    userid = request.COOKIES['userid']
    user = getUser(request)
    try:
        uuid.UUID(id)
    except:
        return render(request, 'badrequest.html', _badRequestContext(request,"The page does not exist."))
    try:
        activity=StudyActivity.objects.get(pk=id)
    except StudyActivity.DoesNotExist:
        return render(request, 'badrequest.html', _badRequestContext(request,"The page does not exist."))
    if activity.tasks.all()[0].assessment.module.semester.user != user:
        return render(request, 'badrequest.html', _badRequestContext(request,"You don't have permission to view this page."))
    notes = list()
    tasks = list()
    options = list()
    for n in activity.note_set.all():
        item = {'note' : n.notes, 'date' : n.date, 'id' : n.uid }
        notes.append(item)
    for t in activity.tasks.all():
        item = {'name' : t.name, 'id' : t.uid }
        tasks.append(item)
    assessment = activity.tasks.all()[0].assessment
    alltasks = assessment.studytask_set.all()
    t1 = activity.tasks.all()
    task_options = alltasks.difference(t1)
    for o in task_options:
        item = {'name' : o.name, 'id' : o.uid }
        options.append(item)
    progress = int(activity.progress()*100)
    activity_info = {
        'uid':activity.uid,
        'name' : activity.name,
        'assessment' : assessment.name,
        'assessment_id' : assessment.uid,
        'type' : activity.get_type_act_display(),
        'progress' : progress,
        'completed' : activity.completed,
        'target' : activity.target,
        'units' : 'requirements', #change this later
        'notes' : notes,
        'tasks' : tasks,
        'options' : options,
    }
    context = {
        'navigation': navigation_list,
        'active': 'Deadlines',
        'user': getUser(request),
        'semesters': _getAllSemesters(request),
        'activity' : activity_info
    }
    return render(request, 'activity.html', context)

def ganttchart(request):
    user = getUser(request)
    modules = Module.objects.filter(semester=user.activeSemester)

    ganttdata = {}
    for module in modules:
        ganttdata[str(module.code)] = {}
        ganttdata[str(module.code)]['name'] = module.name
        ganttdata[str(module.code)]['description'] = module.description
        ganttdata[str(module.code)]['assessments'] = []
        assessments = Assessment.objects.filter(module=module)
        for assessment in assessments:
            a = {}
            a['name'] = assessment.name
            a['description'] = assessment.description
            a['weight'] = assessment.weight
            a['startDate'] = str(assessment.startDate)
            a['deadline'] = str(assessment.deadline)
            a['assessmentType'] = assessment.type_a
            a['tasks'] = []
            a['milestones'] = []
            tasks = StudyTask.objects.filter(assessment=assessment) 
            for task in tasks:
                t = {}
                t['id'] = str(task.uid)
                t['name'] = task.name
                t['description'] = task.description
                t['duration'] = task.duration.days
                t['dependencies'] = []
                for dependency in task.requiredTasks.all():
                    t['dependencies'].append(str(dependency.uid))
                a['tasks'].append(t)
            milestones = Milestone.objects.filter(assessment=assessment)
            for milestone in milestones:
                m = {}
                m['name'] = milestone.name
                m['tasks'] = []
                for mt in milestone.requiredTasks.all():
                    m['tasks'].append(str(mt.uid))
                a['milestones'].append(m)
            ganttdata[str(module.code)]['assessments'].append(a)
            

    context = {
        'navigation': navigation_list,
        'active': 'Gantt Chart',
        'semesters': _getAllSemesters(request),
        'user': getUser(request),
        'ganttdata': json.dumps(ganttdata)
    }
    return render(request, 'ganttchart.html', context)

def milestone(request, id=None):
    if not isLoggedIn(request):
        return redirect('/')
    userid = request.COOKIES['userid']
    user = getUser(request)
    try:
        uuid.UUID(id)
    except:
        return render(request, 'badrequest.html', _badRequestContext(request,"The page does not exist."))
    try:
        milestone=Milestone.objects.get(pk=id)
    except Milestone.DoesNotExist:
        return render(request, 'badrequest.html', _badRequestContext(request,"The page does not exist."))
    if milestone.assessment.module.semester.user != user:
        return render(request, 'badrequest.html', _badRequestContext(request,"You don't have permission to view this page."))
    tasks = list()
    options = list()
    for t in milestone.requiredTasks.all():
        item = {'name' : t.name, 'id' : t.uid }
        tasks.append(item)
    assessment = milestone.assessment
    alltasks = assessment.studytask_set.all()
    t1 = milestone.requiredTasks.all()
    task_options = alltasks.difference(t1)
    for o in task_options:
        item = {'name' : o.name, 'id' : o.uid }
        options.append(item)
    status_img = "img/icon_cross.png"
    if(milestone.hasBeenReached()):
        status_img = "img/icon_check.png"
    milestone_info = {
        'uid':milestone.uid,
        'name' : milestone.name,
        'assessment' : assessment.name,
        'assessment_id' : assessment.uid,
        'status': status_img,
        'tasks' : tasks,
        'options' : options,
    }
    context = {
        'navigation': navigation_list,
        'active': 'Deadlines',
        'user': getUser(request),
        'semesters': _getAllSemesters(request),
        'milestone' : milestone_info
    }
    return render(request, 'milestone.html', context)

def module(request):
    if not isLoggedIn(request):
        return redirect('/')
    user = User.objects.get(userid=request.COOKIES['userid']) #Gets current user
    semester = user.activeSemester
    modules = semester.allModules() #Gets all modules
    completeList = list()

    #Iterates through each module
    for module in modules:
        moduleName = module.name
        moduleCode = module.code
        moduleDesc = module.description

        #Appends each module into completeList
        items = [moduleName, moduleCode, moduleDesc]
        completeList.append(items)

    context = {
        'navigation': navigation_list,
        'active': 'Modules',
        'user': getUser(request),
        'semesters': _getAllSemesters(request),
        'modules': completeList
    }
    return render(request, 'module.html', context)

def moduleInformation(request):
    if not isLoggedIn(request):
        return redirect('/')
    #Used to get module code from URL parameter
    code = request.GET['code']

    user = User.objects.get(userid=request.COOKIES['userid']) #Gets current user
    semester = user.activeSemester
    if not Module.objects.filter(code=code,semester=semester).exists():
        return render(request, 'badrequest.html', _badRequestContext(request,"The page does not exist."))
    module = Module.objects.filter(code=code,semester=semester)[0]
    name = module.name
    desc = module.description
    assessments = module.assessment_set.all()
    completeList = list()

    for assessment in assessments:
        assessmentType = assessment.get_type_a_display()
        assessmentName = assessment.name
        assessmentWeight = assessment.weight
        assessmentStart = assessment.startDate
        assessmentDeadline = assessment.deadline

        items = {'assessmentName': assessmentName, 'assessmentWeight': assessmentWeight, 
                'assessmentStart': assessmentStart, 'assessmentDeadline': assessmentDeadline, 'assessmentid' : assessment.uid}
        print(assessmentDeadline)
        completeList.append(items)

    
    context = {
        'navigation': navigation_list,
        'active': 'ModuleInformation',
        'semesters': _getAllSemesters(request),
        'user' : getUser(request),
        'name': name,
        'code': code,
        'desc': desc,
        'assessments': completeList
    }
    return render(request, 'moduleInformation.html', context)

def _badRequestContext(request,message):
    context = { 'navigation': navigation_list,
                'active': 'Deadlines',
                'semesters': _getAllSemesters(request),
                'user': getUser(request),
                'message': message }
    return context