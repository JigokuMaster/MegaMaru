#include <s32std.h>
#include <eikenv.h>
#include <aknwaitdialog.h>
#include <aknprogressdialog.h>
#include <eikprogi.h>
#include <aknenv.h>
#include <aknappui.h>
#include <aknapp.h>
#include <f32file.h>
#include <avkon.rsg>
#include <uiext.rsg>
#include <eiklbx.h>
#include <gulicon.h> 
#include <eikclbd.h>
#include <aknlists.h>
#include <aknquerydialog.h>
#include <aknmessagequerydialog.h>
#include <Python.h>
#include <symbian_python_ext_util.h>


static int rsc_offset = -1;

NONSHARABLE_CLASS(CDialogObserver): public MProgressDialogCallback
{
    public:
	CDialogObserver(PyObject* aCb);
	//virtual ~CDialogObserver();
	virtual void DialogDismissedL(const TInt aButtonId);
	TBool DialogDismissed();
	void SetDismissState(TInt aValue);

    private:
	PyObject* iCb;
	TInt iDismissState;

};


CDialogObserver::CDialogObserver(PyObject* aCb)
{
    iCb = aCb;
    iDismissState = 0;
    Py_XINCREF(iCb);
}


//CDialogObserver::~CDialogObserver(){}

void CDialogObserver::DialogDismissedL(const TInt aButtonId)
{
    iDismissState = 1;

    if(iCb != NULL)
    {
#ifdef PY22
	PyEval_RestoreThread(PYTHON_TLS->thread_state);
#else 
	PyGILState_STATE gstate = PyGILState_Ensure();

#endif

	PyObject* arg = Py_BuildValue("(i)", aButtonId);	 
	PyObject* tmp_r = PyEval_CallObject(iCb , arg);
	Py_DECREF(arg);
	if(!tmp_r)
	{
	    PyErr_Print();
	}
	else
	{
	    Py_XDECREF(tmp_r);

	}
	Py_XDECREF(iCb);

#ifdef PY22
	PyEval_SaveThread();
#else
	PyGILState_Release(gstate);
#endif
    }

}


TBool CDialogObserver::DialogDismissed()
{
    return iDismissState > 0;
}

void CDialogObserver::SetDismissState(TInt aValue)
{
    iDismissState = aValue;
}


typedef struct WaitDialogObject
{
    PyObject_VAR_HEAD 
	CAknWaitDialog* d;
    CDialogObserver* obs;
    PyObject* cancel_cb;
    TBool running;

}WaidDialogObject;

#define WaitDialogType ((PyTypeObject*)SPyGetGlobalString("WaitDialogType"))

static PyObject* wd_new(PyObject *self, PyObject* args)
{

    WaitDialogObject* obj = NULL;
    TInt resId = R_WAITDIALOG_SOFTKEY_CANCEL;
    PyObject* text = NULL;
    PyObject* cb = NULL;
    if (!PyArg_ParseTuple(args, "|iOO",&resId, &text, &cb))
    {
	return NULL;
    }

    if ((cb != NULL) && !PyCallable_Check(cb))
    {

	PyErr_SetString(PyExc_TypeError, "callable expected");

	return NULL;

    }

    if (!(obj = PyObject_New(WaitDialogObject, WaitDialogType)))
    {
	return PyErr_NoMemory();
    }

    CAknWaitDialog* wd = new (ELeave) CAknWaitDialog(NULL, ETrue);
    //wd = new (ELeave) CAknWaitDialog(reinterpret_cast<CEikDialog**>(&wd));
    if(!wd)
    {
	return PyErr_NoMemory();
    }

    CDialogObserver* obs = new (ELeave) CDialogObserver(cb);
    if(!obs)
    {
	delete wd;
	return PyErr_NoMemory();
    }

    wd->SetCallback(obs);
    if(text && PyUnicode_Check(text))
    {

	TPtrC textPtr((TUint16*) PyUnicode_AsUnicode(text), PyUnicode_GetSize(text));
	TRAPD(error, wd->SetTextL(textPtr));
	if (error != KErrNone)
	{
	    return SPyErr_SetFromSymbianOSErr(error);
	}

    }

    wd->PrepareLC(resId);
    obj->d = wd;
    obj->obs = obs;
    obj->cancel_cb = cb;
    obj->running = EFalse;
    return (PyObject*)obj;
}


static PyObject* wd_show(WaitDialogObject *self, PyObject* args)
{

    if(self->running)
    {
	Py_INCREF(Py_None);
	return Py_None;		
    }

    self->running = ETrue;
    self->obs->SetDismissState(0);
    TInt ret = self->d->RunLD();
    return Py_BuildValue("i", ret);
}

static PyObject* wd_finish(WaitDialogObject *self, PyObject* args)
{

    if( (self->d != NULL) && (!self->obs->DialogDismissed()) && self->running)
    {
	TRAPD(error, self->d->ProcessFinishedL());
	if (error != KErrNone)
	{
	    return SPyErr_SetFromSymbianOSErr(error);
	}
    }


    self->running = EFalse;
    self->obs->SetDismissState(1);
    Py_INCREF(Py_None);   
    return Py_None;

}

static PyObject* wd_set_text(WaitDialogObject *self, PyObject* args)
{

    PyObject* text = NULL;
    if (!PyArg_ParseTuple(args, "O", &text))
    {
	return NULL;
    }

    if(PyUnicode_Check(text))
    {

	TPtrC textPtr((TUint16*) PyUnicode_AsUnicode(text), PyUnicode_GetSize(text));

	TRAPD(error, self->d->SetTextL(textPtr));

	if (error != KErrNone)
	{
	    return SPyErr_SetFromSymbianOSErr(error);
	}

    }

    Py_INCREF(Py_None);   
    return Py_None;

}



const static PyMethodDef wd_methods[] = 
{
    {"show", (PyCFunction)wd_show, METH_VARARGS},
    /*{"setTitle", (PyCFunction)wd_set_title, METH_VARARGS},*/
    {"setText", (PyCFunction)wd_set_text, METH_VARARGS},
    {"finish", (PyCFunction)wd_finish, METH_NOARGS},
    {NULL, NULL}
};


static void wd_dealloc(WaitDialogObject *obj)
{
    PyObject_Del(obj);
}


static PyObject * wd_getattr(WaitDialogObject* obj, char *name)
{
    return Py_FindMethod((PyMethodDef*)wd_methods, (PyObject*)obj, name);
}



static int wd_setattr(WaitDialogObject* obj, char *name, PyObject *v)
{
    return 0;
}



static PyTypeObject c_wd_type = 
{

    PyObject_HEAD_INIT(NULL)
	0,                                         /*ob_size*/
    "uiext.WaitDialog",                             /*tp_name*/
    sizeof(WaitDialogObject),                     /*tp_basicsize*/
    0,                                         /*tp_itemsize*/
    /* methods */
    (destructor)wd_dealloc,                /*tp_dealloc*/
    0,                                         /*tp_print*/
    (getattrfunc)wd_getattr,               /*tp_getattr*/
    (setattrfunc)wd_setattr,               /*tp_setattr*/
    0,                                         /*tp_compare*/
    0,                                         /*tp_repr*/
    0,                                         /*tp_as_number*/
    0,                                         /*tp_as_sequence*/
    0,                                         /*tp_as_mapping*/
    0,                                         /*tp_hash*/

};


typedef struct ProgressDialogObject
{
    PyObject_VAR_HEAD 
	CAknProgressDialog* d;
    CDialogObserver* obs;
    PyObject* cancel_cb;
    TBool running;
}ProgressDialogObject;


#define ProgressDialogType ((PyTypeObject*)SPyGetGlobalString("ProgressDialogType"))


static PyObject* pd_new(PyObject *self, PyObject* args)
{

    ProgressDialogObject* obj = NULL;
    TInt resId = R_PROGRESSDIALOG_SOFTKEY_CANCEL;
    PyObject* text = NULL;
    PyObject* cb = NULL;

    if (!PyArg_ParseTuple(args, "|iOO" ,&resId, &text, &cb))
    {
	return NULL;
    }

    if ((cb != NULL) && !PyCallable_Check(cb))

    {

	PyErr_SetString(PyExc_TypeError, "callable expected");

	return NULL;

    }

    if (!(obj = PyObject_New(ProgressDialogObject, ProgressDialogType)))
    {
	return PyErr_NoMemory();
    }

    CAknProgressDialog* pd = new (ELeave) CAknProgressDialog(NULL);
    //pd = new (ELeave) CAknProgressDialog(reinterpret_cast<CEikDialog**>(&pd));
    if(!pd)
    {
	return PyErr_NoMemory();
    }

    CDialogObserver* obs = new (ELeave) CDialogObserver(cb);
    if(!obs)
    {
	delete pd;
	return PyErr_NoMemory();
    }

    pd->SetCallback(obs);
    if(text && PyUnicode_Check(text))
    {

	TPtrC textPtr((TUint16*) PyUnicode_AsUnicode(text), PyUnicode_GetSize(text));

	TRAPD(error, pd->SetTextL(textPtr));

	if (error != KErrNone)
	{
	    return SPyErr_SetFromSymbianOSErr(error);
	}

    }

    pd->PrepareLC(resId);
    obj->d = pd;
    obj->obs = obs;
    obj->cancel_cb = cb;
    obj->running = EFalse;
    return (PyObject*)obj;
}


static PyObject* pd_show(ProgressDialogObject *self, PyObject* args)
{
    if(self->running)
    {
	Py_INCREF(Py_None);   
	return Py_None;
    }	

    PyObject* text = NULL;
    int max_val = 100;

    if (!PyArg_ParseTuple(args, "|Oi", &text, &max_val))
    {
	return NULL;
    }


    if(text && PyUnicode_Check(text))
    {

	TPtrC textPtr((TUint16*)PyUnicode_AsUnicode(text), PyUnicode_GetSize(text));

	TRAPD(error, self->d->SetTextL(textPtr));

	if (error != KErrNone)
	{
	    return SPyErr_SetFromSymbianOSErr(error);
	}

    }


    TRAPD(error, {

	    CEikProgressInfo* pinfo = self->d->GetProgressInfoL();
	    pinfo->SetFinalValue(max_val);
	    }
	 );

    if (error != KErrNone)
    {
	delete self->d;
	return SPyErr_SetFromSymbianOSErr(error);
    }

    self->running = ETrue;
    self->obs->SetDismissState(0);
    TInt ret = self->d->RunLD();  
    return Py_BuildValue("i", ret);
}

static PyObject* pd_finish(ProgressDialogObject *self, PyObject* args)
{

    if((self->d != NULL) && (!self->obs->DialogDismissed()) && self->running)
    {
	TRAPD(error, self->d->ProcessFinishedL());
	if (error != KErrNone)
	{
	    return SPyErr_SetFromSymbianOSErr(error);
	}
    }

    self->running = EFalse;
    self->obs->SetDismissState(1);
    Py_INCREF(Py_None);   
    return Py_None;

}


static PyObject* pd_set_text(ProgressDialogObject *self, PyObject* args)
{

    if((!self->d) || (self->obs->DialogDismissed()) || !self->running)
    {
	Py_INCREF(Py_None);
	return Py_None;
    }

    PyObject* text = NULL;
    if (!PyArg_ParseTuple(args, "O", &text))
    {
	return NULL;
    }

    if(PyUnicode_Check(text))
    {

	TPtrC textPtr((TUint16*) PyUnicode_AsUnicode(text), PyUnicode_GetSize(text));

	TRAPD(error, self->d->SetTextL(textPtr));

	if (error != KErrNone)
	{
	    return SPyErr_SetFromSymbianOSErr(error);
	}

    }

    Py_INCREF(Py_None);   
    return Py_None;

}

static PyObject* pd_update(ProgressDialogObject *self, PyObject* args)
{

    if((!self->d) || (self->obs->DialogDismissed()) || !self->running)
    {
	Py_INCREF(Py_None);
	return Py_None;
    }

    int v;
    PyObject* text = NULL;
    int cur_val = 0;
    int max_val = 0;
    if (!PyArg_ParseTuple(args, "i|Oi", &v, &text, &cur_val, &max_val))
    {
	return NULL;
    }


    if(text && PyUnicode_Check(text))
    {

	TPtrC textPtr((TUint16*) PyUnicode_AsUnicode(text), PyUnicode_GetSize(text));

	TRAPD(error, self->d->SetTextL(textPtr));

	if (error != KErrNone)
	{
	    return SPyErr_SetFromSymbianOSErr(error);
	}

    }


    TRAPD(error, {

	    CEikProgressInfo* pinfo = self->d->GetProgressInfoL();

	    if(max_val > 0)
	    {
	    pinfo->SetFinalValue(max_val);
	    }

	    if(cur_val > 0)
	    {
	    pinfo->SetAndDraw(cur_val);
	    }

	    else if(v > 0)
	    {
	    pinfo->IncrementAndDraw(v);
	    }
	    });

    if(error != KErrNone)
    {
	delete self->d;
	return SPyErr_SetFromSymbianOSErr(error);
    }
    Py_INCREF(Py_None);   
    return Py_None;

}


const static PyMethodDef pd_methods[] = 
{
    {"show", (PyCFunction)pd_show, METH_VARARGS},

    {"setText", (PyCFunction)pd_set_text, METH_VARARGS},

    {"update", (PyCFunction)pd_update, METH_VARARGS},

    {"finish", (PyCFunction)pd_finish, METH_NOARGS},
    {NULL, NULL}
};




static void pd_dealloc(ProgressDialogObject *obj)
{
    PyObject_Del(obj);
}


static PyObject * pd_getattr(ProgressDialogObject* obj, char *name)
{
    return Py_FindMethod((PyMethodDef*)pd_methods, (PyObject*)obj, name);
}



static int pd_setattr(ProgressDialogObject* obj, char *name, PyObject *v)
{
    return 0;
}




static PyTypeObject c_pd_type = 
{

    PyObject_HEAD_INIT(NULL)
	0,                                         /*ob_size*/
    "uiext.ProgressDialog",                             /*tp_name*/
    sizeof(ProgressDialogObject),                     /*tp_basicsize*/
    0,                                         /*tp_itemsize*/
    /* methods */
    (destructor)pd_dealloc,                /*tp_dealloc*/
    0,                                         /*tp_print*/
    (getattrfunc)pd_getattr,               /*tp_getattr*/
    (setattrfunc)pd_setattr,               /*tp_setattr*/
    0,                                         /*tp_compare*/
    0,                                         /*tp_repr*/
    0,                                         /*tp_as_number*/
    0,                                         /*tp_as_sequence*/
    0,                                         /*tp_as_mapping*/
    0,                                         /*tp_hash*/

};


PyObject* tqd_show(PyObject* self, PyObject* args)
{
    int l_label;
    int max_len = 1024;
    char *b_label;
    PyObject* inival = NULL;
    PyObject* retval = NULL;

    if (!PyArg_ParseTuple(args, "u#|Oi", &b_label, &l_label, &inival, &max_len))
	return NULL;

    TInt error = KErrNone;
    CAknQueryDialog* dlg = NULL;
    TPtr buf(NULL, 0);
    if (retval = PyUnicode_FromUnicode(NULL, max_len))
    {
	buf.Set(PyUnicode_AsUnicode(retval), 0, max_len);
	if (inival && PyUnicode_Check(inival))
	{
	    buf.Copy(PyUnicode_AsUnicode(inival), PyUnicode_GetSize(inival));
	}


      TRAP(error, {
        dlg = CAknTextQueryDialog::NewL(buf, CAknQueryDialog::ENoTone);
        ((CAknTextQueryDialog*)dlg)->SetMaxLength(max_len);
      });
      if (error == KErrNone)
        dlg->SetPredictiveTextInputPermitted(ETrue);
    }
    else
    {
      error = KErrPython;
    }
    

    TInt user_response = 0;
    if (error == KErrNone)
    {
    
	TRAP(error, {
		dlg->SetPromptL(TPtrC((TUint16 *)b_label, l_label));
		Py_BEGIN_ALLOW_THREADS  
		user_response = dlg->ExecuteLD(R_TEXT_DIALOGQUERY);
		Py_END_ALLOW_THREADS
      });
  }

  if (error != KErrNone)
  {
    delete dlg;
    Py_XDECREF(retval);
    return SPyErr_SetFromSymbianOSErr(error);
  }
  else if (!user_response)
  {
    Py_XDECREF(retval);
    Py_INCREF(Py_None);
    return Py_None;
  }
  else 
  {
      PyUnicode_Resize(&retval, buf.Length());
  }
  return retval;
}


PyObject* msgqd_show(PyObject* self, PyObject* args)
{
    int l_label, l_msg;
    char *b_label, *b_msg;

    if (!PyArg_ParseTuple(args, "u#u#", &b_label, &l_label, &b_msg, &l_msg))
	return NULL;

    TPtrC label_ptr((TUint16 *)b_label, l_label);
    TPtrC msg_ptr((TUint16 *)b_msg, l_msg);

    TInt error = KErrNone;
    CAknMessageQueryDialog* dlg = NULL;
    /*if (!(dlg = new CAknMessageQueryDialog))
    {
	return PyErr_NoMemory();
    }*/

    TRAP(error, {

	    dlg = CAknMessageQueryDialog::NewL(msg_ptr);
	    dlg->PrepareLC(R_AVKON_MESSAGE_QUERY_DIALOG);
	    dlg->ButtonGroupContainer().MakeCommandVisible(EAknSoftkeyCancel, EFalse);
	    dlg->SetHeaderTextL(label_ptr);
	    //dlg->SetMessageTextL(msg_ptr);
	    Py_BEGIN_ALLOW_THREADS
	    dlg->RunLD();
	    Py_END_ALLOW_THREADS
    });
    
    /*if (error == KErrNone)
    {
	Py_BEGIN_ALLOW_THREADS
	TRAP(error, dlg->RunLD());
	Py_END_ALLOW_THREADS
    }*/

    RETURN_ERROR_OR_PYNONE(error);
}




PyObject* set_cba_label(PyObject* self, PyObject* args)
{

    PyObject* label = NULL;
    TInt aId;
    if (!PyArg_ParseTuple(args, "Ui", &label, &aId))
    {
	return NULL;
    }


    CEikButtonGroupContainer* cba = CEikButtonGroupContainer::Current();
    if(cba)
    {

	TPtrC textPtr((TUint16*) PyUnicode_AsUnicode(label), PyUnicode_GetSize(label));

	TRAPD(error, cba->SetCommandL(aId, textPtr));

	if(error != KErrNone)
	{
	    return SPyErr_SetFromSymbianOSErr(error);
	}	
	cba->DrawNow();
    }

    Py_INCREF(Py_None);   
    return Py_None;
}

PyObject* set_cba(PyObject* self, PyObject* args)
{

    TInt aId;
    if (!PyArg_ParseTuple(args, "i", &aId))
    {
	return NULL;
    }


    CEikButtonGroupContainer* cba = CEikButtonGroupContainer::Current();
    if(cba)
    {

	TRAPD(error, cba->SetCommandSetL(aId));

	if(error != KErrNone)
	{
	    return SPyErr_SetFromSymbianOSErr(error);
	}	
	cba->DrawNow();
    }

    Py_INCREF(Py_None);   
    return Py_None;
}


#ifndef PY22
class CAppuifwEventBindingArray;
class CAppuifwEventBindingArray;
class CListBoxCallback;
enum ListboxType {ESingleListbox, EDoubleListbox, ESingleGraphicListbox, EDoubleGraphicListbox };
enum ControlName {EListbox=0, EText, ECanvas, EGLCanvas};


struct Listbox_object {
    PyObject_VAR_HEAD
	CEikListBox *ob_control;
    CAppuifwEventBindingArray* ob_event_bindings;
    ControlName control_name;
    ListboxType ob_lb_type;
    CListBoxCallback *ob_listbox_callback;
    CArrayPtrFlat<CGulIcon>* ob_icons;
};

PyObject* clear_listbox(PyObject* self, PyObject* args)
{

    Listbox_object* obj;    
    if (!PyArg_ParseTuple(args, "O", &obj))
    {
	return NULL;
    }

    if(strcmp(((PyObject*)obj)->ob_type->tp_name, "appuifw.Listbox") != 0)
    {

	PyErr_SetString(PyExc_TypeError, "object must be type of appuifw.Listbox");

	return NULL;
    }

    CDesCArray *itemsArray = NULL;
    if(obj->ob_lb_type == ESingleListbox)
    {
	CAknSingleStyleListBox* sslb = STATIC_CAST(CAknSingleStyleListBox*, obj->ob_control);

	itemsArray = STATIC_CAST(CDesCArray*, sslb->Model()->ItemTextArray());

	sslb->Reset();


    }

    else if(obj->ob_lb_type == EDoubleListbox)
    {
	CAknDoubleStyleListBox* dslb = STATIC_CAST(CAknDoubleStyleListBox*, obj->ob_control);

	itemsArray = STATIC_CAST(CDesCArray*, dslb->Model()->ItemTextArray());

	dslb->Reset();

    }

    if(itemsArray != NULL)
    {
	itemsArray->Reset();
    }

    Py_INCREF(Py_None);   
    return Py_None;
}
#endif




static PyMethodDef mod_methods[] = {
    {"WaitDialog", wd_new, METH_VARARGS, ""},
    {"ProgressDialog", pd_new, METH_VARARGS, ""},
    {"TextQueryDialog", tqd_show, METH_VARARGS, ""},
    {"MessageQueryDialog", msgqd_show, METH_VARARGS, ""}, 
    {"setSoftKeyLabel", set_cba_label, METH_VARARGS, ""},
    {"setSoftKey", set_cba, METH_VARARGS, ""},
#ifndef PY22
    {"clearListBox", clear_listbox, METH_VARARGS, ""},
#endif
    {NULL, NULL, 0, NULL},
};



#define DEFTYPE(name,type_template)  do {				\
    PyTypeObject* tmp = PyObject_New(PyTypeObject, &PyType_Type);	\
    *tmp = (type_template);						\
    tmp->ob_type = &PyType_Type;					\
    SPyAddGlobalString((name), (PyObject*)tmp);				\
} while (0)

extern "C" {

    DL_EXPORT(void) inituiext()
    {
	_LIT(KRscFile, "\\resource\\apps\\uiext.rsc");
	CEikonEnv* env = CEikonEnv::Static();
	CEikAppUi* appui = env->EikAppUi();     
	TParse f;
	TFileName fn = appui->Application()->AppFullName();
	f.Set(KRscFile, &fn, NULL);

	TRAPD(error, rsc_offset = env->AddResourceFileL(f.FullName()));
	if(error != KErrNone)
	{
	    SPyErr_SetFromSymbianOSErr(error);
	    return;
	}

	DEFTYPE("WaitDialogType",c_wd_type);
	DEFTYPE("ProgressDialogType",c_pd_type);
	PyObject* m = Py_InitModule3("uiext", mod_methods,"");

	PyModule_AddIntConstant(m,"R_WAITDIALOG_SOFTKEY_CANCEL", R_WAITDIALOG_SOFTKEY_CANCEL);
	PyModule_AddIntConstant(m,"R_WAITDIALOG", R_WAITDIALOG);
	PyModule_AddIntConstant(m,"R_MODAL_WAITDIALOG", R_MODAL_WAITDIALOG);
	PyModule_AddIntConstant(m,"R_PROGRESSDIALOG", R_PROGRESSDIALOG);
	PyModule_AddIntConstant(m,"R_PROGRESSDIALOG_SOFTKEY_CANCEL", R_PROGRESSDIALOG_SOFTKEY_CANCEL);
	PyModule_AddIntConstant(m,"R_MODAL_PROGRESSDIALOG", R_MODAL_PROGRESSDIALOG);
	PyModule_AddIntConstant(m,"EAknSoftkeyExit", EAknSoftkeyExit);
	PyModule_AddIntConstant(m,"EAknSoftkeyExit", EAknSoftkeyExit);
	PyModule_AddIntConstant(m,"EAknSoftkeyBack", EAknSoftkeyBack);
	PyModule_AddIntConstant(m,"EAknSoftkeyCancel", EAknSoftkeyCancel);
	PyModule_AddIntConstant(m,"EAknSoftkeyClose", EAknSoftkeyClose);
	PyModule_AddIntConstant(m,"EAknSoftkeyQuit", EAknSoftkeyQuit);
	PyModule_AddIntConstant(m,"EAknSoftkeyOptions", EAknSoftkeyOptions);     
	PyModule_AddIntConstant(m,"R_AVKON_SOFTKEYS_OPTIONS_BACK", R_AVKON_SOFTKEYS_OPTIONS_BACK);
	PyModule_AddIntConstant(m,"R_AVKON_SOFTKEYS_OPTIONS_EXIT", R_AVKON_SOFTKEYS_OPTIONS_EXIT);
	PyModule_AddIntConstant(m,"R_AVKON_SOFTKEYS_QUIT", R_AVKON_SOFTKEYS_QUIT); 
	PyModule_AddIntConstant(m,"R_AVKON_SOFTKEYS_EXIT", R_AVKON_SOFTKEYS_EXIT); 

    }

    DL_EXPORT(void) unloaduiext(void* p)
    {
	if(rsc_offset != (-1))
	{
	    CEikonEnv::Static()->DeleteResourceFile(rsc_offset);
	}
    }
}
// EOF
