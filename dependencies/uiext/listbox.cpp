#include <aknlists.h>
#include <eiklbx.h>
#include <eikclbd.h>
#include <akntitle.h>
#include <aknsfld.h>
#include <eikdialg.h>
#include <AknDlgShut.h>
#include <aknselectionlist.h>
#include <avkon.rsg>
#include <uiext.rsg>
#include "listbox.h"


#define RETURN_IF_ERROR(error) \
    if(error != KErrNone){ \
	return SPyErr_SetFromSymbianOSErr(error); } \


#define EListBoxDialogMenuItemBaseId 0x6008
#define EListBoxDialogMaxMenuItems 30
#define KMaxListBoxDialog 1024

class CListBoxDialog: public CAknSelectionListDialog
{

    public:
	CListBoxDialog(TInt aIndex, MDesCArray *aArray, MEikCommandObserver *aCommand=0):
	    CAknSelectionListDialog(aIndex, aArray, 0)
	{
	    
	    iSearchField = NULL;
	    iMenuEventsCallback = NULL;
	    iKeyEventsCallback = NULL;
	    iListBoxEventsCallback = NULL;
	    iExitCallback = NULL;
	    iDynInitMenuCallback = NULL;
	    iMenuItems = NULL;
	    iThreadState = NULL;
	}

	virtual ~CListBoxDialog()
	{
	    if(iSearchField)
		delete iSearchField;

	    if(iMenuEventsCallback)
		Py_XDECREF(iMenuEventsCallback);

	    if(iKeyEventsCallback)
		Py_XDECREF(iKeyEventsCallback);

	    if(iListBoxEventsCallback)
		Py_XDECREF(iListBoxEventsCallback);

	    if(iExitCallback)
		Py_XDECREF(iExitCallback);

	    if(iDynInitMenuCallback)
		Py_XDECREF(iDynInitMenuCallback);

	    if(iMenuItems)
		Py_XDECREF(iMenuItems);

	    RestoreThread();
	}

	TInt RunLD()
	{
	    SaveThread();
	    return CAknSelectionListDialog::RunLD();
	}

	void SaveThread()
	{
	    iThreadState = PyEval_SaveThread();
	}

	void RestoreThread()
	{
	    if (iThreadState)
	    	PyEval_RestoreThread(iThreadState);
	}

	void SetMenuEventsCallback(PyObject* aCallback)
	{
	    if(aCallback)
		iMenuEventsCallback = aCallback;
		Py_XINCREF(iMenuEventsCallback);
	}

	void SetExitCallback(PyObject* aCallback)
	{
	    if(aCallback)
		iExitCallback = aCallback;
		Py_XINCREF(iExitCallback);
	}

	void SetListBoxEventsCallback(PyObject* aCallback)
	{
	    if(aCallback)
		iListBoxEventsCallback = aCallback;
		Py_XINCREF(iListBoxEventsCallback);
	}

	void SetDynInitMenuCallback(PyObject* aCallback)
	{
	    if(aCallback)
		iDynInitMenuCallback = aCallback;
		Py_XINCREF(iDynInitMenuCallback);
	}

	void UnSetMenuItems()
	{
	    if(iMenuItems)
		Py_XDECREF(iMenuItems);
		iMenuItems = NULL;
	}
	void SetMenuItems(PyObject* aItems)
	{

	    if(aItems)
		UnSetMenuItems();
		iMenuItems = aItems;
		Py_XINCREF(iMenuItems);
	}

	void SetSoftKeyVisible(TInt aId, TBool aVisible)
	{
	    ButtonGroupContainer().MakeCommandVisible(aId, aVisible);
	}

	void SetKeyEventsCallback(PyObject* aCallback)
	{
	    if(aCallback)
		iKeyEventsCallback = aCallback;
		Py_XINCREF(iKeyEventsCallback);
	}

	CEikListBox* GetListBox()
	{
	    return ListBox();
	}

	void EnableMarqueeL(TBool aEnable, TInt aListBoxStyle)
	{
	    if(aListBoxStyle == EDoubleGraphicListbox || aListBoxStyle == EDoubleListbox)
	    {	
		((CEikFormattedCellListBox*)ListBox())->ItemDrawer()->FormattedCellData()->EnableMarqueeL(aEnable);
	    }
	    else{
		((CAknColumnListBox*)ListBox())->ItemDrawer()->ColumnData()->EnableMarqueeL(aEnable);
	    }
	}

	void EnableSearchFieldL(TBool aEnable)
	{
	    /*if(iSearchField == NULL)
	    {
		CEikListBox* iListBox = ListBox();
		iSearchField = CAknSearchField::NewL(*iListBox, CAknSearchField::EFixed, NULL, 120);
		CleanupStack::PushL(iSearchField);
		CAknFilteredTextListBoxModel* model = static_cast<CAknFilteredTextListBoxModel*>(iListBox->Model());
		model->CreateFilterL(iListBox, iSearchField);
		CleanupStack::PushL(iSearchField);
	    }

	    iSearchField->MakeVisible(aEnable);
	    */
	}


	void UpdateTitle()
	{
	    CEikonEnv* env = CEikonEnv::Static();
	    CAknTitlePane* tp = (CAknTitlePane*)((env->AppUiFactory()->StatusPane())->ControlL(TUid::Uid(EEikStatusPaneUidTitle)));
	    if (tp && iTitle.Length()>0)
	    	TRAP_IGNORE(tp->SetTextL(iTitle)); 
	    
	}

	void SetTitle(TPtrC& aTitle)
	{
	    iTitle.Copy(aTitle);
	    UpdateTitle();
	}


	void FocusChanged(TDrawNow aDrawNow)
	{
	    CAknSelectionListDialog::FocusChanged(aDrawNow);
	    UpdateTitle();	    
	}    
	void ProcessCommandL(TInt aCommandId)
	{

	    CAknSelectionListDialog::ProcessCommandL(aCommandId);
	    if(iMenuEventsCallback && aCommandId>=EListBoxDialogMenuItemBaseId)
	    {
		RestoreThread();
		PyObject* arg = Py_BuildValue("(i)", aCommandId-EListBoxDialogMenuItemBaseId);
		PyObject* tmp_r = PyEval_CallObject(iMenuEventsCallback , arg);
		Py_DECREF(arg);
		if(!tmp_r)
		{
		    PyErr_Print();
		}
		else
		{    
		    Py_DECREF(tmp_r);
		}
		SaveThread();
	    }	
	}

	/*virtual*/ TKeyResponse OfferKeyEventL(const TKeyEvent& aKeyEvent, TEventCode aType )
	{

	    if(iKeyEventsCallback && (aType == EEventKey))
	    {
		RestoreThread();
		PyObject* arg = Py_BuildValue("(i)", aKeyEvent.iCode);	 
		PyObject* tmp_r = PyEval_CallObject(iKeyEventsCallback , arg);
		Py_DECREF(arg);		
		if(!tmp_r)
		{
		    PyErr_Print();
		}
		else
		{
		    Py_DECREF(tmp_r);
		}
		SaveThread();	
	
	    }
	    return CAknSelectionListDialog::OfferKeyEventL(aKeyEvent, aType );
	}

	void DynInitMenuPaneL(TInt aResourceId, CEikMenuPane* aMenuPane)
	{
	    CAknSelectionListDialog::DynInitMenuPaneL(aResourceId, aMenuPane);
   
	    if(iMenuItems && aResourceId==R_LISTBOXDIALOG_MENU)
	    {
		RestoreThread();
		TInt error = KErrNone;
		if(PyList_Check(iMenuItems))
		{
		    int sz = PyList_Size(iMenuItems);
		    for (int i = 0; i < sz; i++) {
			PyObject* text =
			PyTuple_GetItem(PyList_GetItem(iMenuItems, i), 0);
			if (!text)
			    break;
			CEikMenuPaneItem::SData item;
			item.iCommandId = (EListBoxDialogMenuItemBaseId)+i;
			item.iCascadeId = 0;
			item.iFlags = 0;
			item.iText.Copy(PyUnicode_AsUnicode(text), Min(PyUnicode_GetSize(text),
					CEikMenuPaneItem::SData::ENominalTextLength));
			item.iExtraText = _L("");

			TRAP(error, aMenuPane->AddMenuItemL(item));
			if (error != KErrNone)
			    break;
		    }
		}

		SaveThread();
		User::LeaveIfError(error);
	    }

	}
    
	void FinishL()
	{

	    CEikonEnv* env = CEikonEnv::Static();
	    AknDialogShutter::ShutDialogsL(*env);
	    /*TKeyEvent keyEvent;	    
	    keyEvent.iCode = EKeyEscape;
	    keyEvent.iModifiers = 0;
	    keyEvent.iRepeats = 1;
	    env->SimulateKeyEventL(keyEvent, EEventKey);*/
	    //TryExitL(EAknSoftkeyExit);
	}

	TBool OkToExitL(TInt aButton)
	{
	    TBool exiting = EFalse;
	    CAknSelectionListDialog::OkToExitL(aButton);
	    switch(aButton)
	    {
		case EAknSoftkeyBack:
		case EAknSoftkeyExit:
		    exiting = ETrue;
		    break;		
	    }

	    if(exiting && iExitCallback)
	    {
		RestoreThread();
		PyObject* tmp_r = PyEval_CallObject(iExitCallback , NULL);
		if(!tmp_r)
		{
		    PyErr_Print();
		}
		else
		{
		    if(PyBool_Check(tmp_r))
			exiting = tmp_r == Py_True;

		    if(PyInt_Check(tmp_r))
			exiting = PyInt_AsLong(tmp_r) == 1;
	    
		    Py_DECREF(tmp_r);
		}
		SaveThread();
	    }
	    return exiting;
	}

    private:
	void HandleListBoxEventL(CEikListBox* aListBox, TListBoxEvent aEventType)
	{
 
	    if (iListBoxEventsCallback && (aEventType == EEventEnterKeyPressed || aEventType == EEventItemDoubleClicked))
	    {
		RestoreThread();
		PyObject* arg = Py_BuildValue("(i)", ListBox()->CurrentItemIndex());	 
		PyObject* tmp_r = PyEval_CallObject(iListBoxEventsCallback , arg);
		Py_DECREF(arg);
		if(!tmp_r)
		{
		    PyErr_Print();
		}
		else
		{
		    Py_DECREF(tmp_r);
		}
		SaveThread();
	    }
	}

    public:
	CAknSearchField* iSearchField;
	PyObject* iListBoxEventsCallback;
	PyObject* iKeyEventsCallback;
	PyObject* iMenuEventsCallback;
	PyObject* iExitCallback;
	PyObject* iDynInitMenuCallback;
	PyObject* iMenuItems;
	PyThreadState* iThreadState;
	TBuf<KMaxListBoxDialog> iTitle;

};

#define ListBoxDialogType ((PyTypeObject*)SPyGetGlobalString("ListBoxDialogType"))


PyObject* ListBoxDialog_create(PyObject* /*self*/, PyObject *args)
{
	ListboxType listbox_type = ESingleListbox;
	PyObject* list;
	PyObject *itemclicks_callback = NULL;
	ListBoxDialogObject *obj;
	TInt error = KErrNone;
	int no_menu = 0;
	if (!PyArg_ParseTuple(args, "O!|iOi", &PyList_Type, &list, &listbox_type, &itemclicks_callback, &no_menu))
		return NULL;

	if (itemclicks_callback)
	{
		if (itemclicks_callback == Py_None)
			itemclicks_callback = NULL;
		else if (!PyCallable_Check(itemclicks_callback)) {
			PyErr_SetString(PyExc_TypeError, "itemclicks callback must be a callable");
			return NULL;
		}
	}

	if (!(obj = PyObject_New(ListBoxDialogObject , ListBoxDialogType)))
	{
	    return PyErr_NoMemory();
	}

	obj->d = NULL;
	obj->d_executed = 0;
	obj->lb_type = listbox_type;
	obj->lb_icons = NULL;
	CDesCArray *items_list = NULL;

	if ( (listbox_type==ESingleGraphicListbox) || (listbox_type==EDoubleGraphicListbox) )
	    TRAP(error, obj->lb_icons = new(ELeave) CArrayPtrFlat<CGulIcon>(5));
	    RETURN_IF_ERROR(error);

	error = create_listbox_items(listbox_type, list, items_list, NULL, obj->lb_icons);	    	
	RETURN_IF_ERROR(error);

	if(!(obj->d = new CListBoxDialog(-1, items_list)) )
	{
	    return PyErr_NoMemory();
	}

	obj->d->SetListBoxEventsCallback(itemclicks_callback);
	TInt menubar = (no_menu == 1) ? R_AVKON_DIALOG_EMPTY_MENUBAR : R_LISTBOXDIALOG_MENUBAR;
	TRAP(error, obj->d->ConstructL(menubar));
	RETURN_IF_ERROR(error);
	TInt res_id = R_SINGLELISTBOX_DIALOG;
	switch(obj->lb_type)
	{
	    case EDoubleListbox:
		res_id = R_DOUBLELISTBOX_DIALOG;
		break;
	    case ESingleGraphicListbox:
		res_id = R_SINGLEGRAPHICLISTBOX_DIALOG;
		break;
	    case EDoubleGraphicListbox:
		res_id = R_DOUBLEGRAPHICLISTBOX_DIALOG;
		break;
	}

	obj->d->PrepareLC(res_id);
	TRAP(error, {
		if (obj->lb_icons != NULL)
		    obj->d->SetIconArrayL(obj->lb_icons);
	    	});

	RETURN_IF_ERROR(error);
	return (PyObject*)obj;
}

static PyObject* ListBoxDialog_show(ListBoxDialogObject *obj, PyObject* args)
{
    if(!obj->d)
    {
	Py_INCREF(Py_None);
	return Py_None;		
    }

    obj->d_executed = 1;
    TInt ret = obj->d->RunLD();
    return Py_BuildValue("i", ret);
}

static PyObject* ListBoxDialog_setTitle(ListBoxDialogObject *obj, PyObject* args)
{
    TInt error = KErrNone;
    if(obj->d)
    {
	int l = 0;
	char *b = NULL;

	if (!PyArg_ParseTuple(args, "u#", &b, &l))
	    return NULL;
	
	TPtrC title((TUint16 *)b, l);
	obj->d->SetTitle(title);
   
    }
    RETURN_ERROR_OR_PYNONE(error);	
}

static PyObject* ListBoxDialog_setMenuCallbacks(ListBoxDialogObject *obj, PyObject* args)
{
    if(obj->d)
    {
	PyObject* events_cb = NULL;
	PyObject* init_cb = NULL;
	if (!PyArg_ParseTuple(args, "O|O", &events_cb, &init_cb))
	    return NULL;

	if (events_cb && !PyCallable_Check(events_cb)) {
	    PyErr_SetString(PyExc_TypeError, "callable expected");
	    return NULL;
	}

	if (init_cb && !PyCallable_Check(init_cb)) {
	    PyErr_SetString(PyExc_TypeError, "callable expected");
	    return NULL;
	}
	obj->d->SetMenuEventsCallback(events_cb);
	obj->d->SetDynInitMenuCallback(init_cb);
    }
    Py_INCREF(Py_None);
    return Py_None;	
}

static PyObject* ListBoxDialog_setKeyEventsCallbacks(ListBoxDialogObject *obj, PyObject* args)
{
    if(obj->d)
    {
	PyObject* cb = NULL;
	if (!PyArg_ParseTuple(args, "O", &cb))
	    return NULL;

	if (cb && !PyCallable_Check(cb)) {
	    PyErr_SetString(PyExc_TypeError, "callable expected");
	    return NULL;
	}
	obj->d->SetKeyEventsCallback(cb);
    }
    Py_INCREF(Py_None);
    return Py_None;	
}

static PyObject* ListBoxDialog_setExitCallbacks(ListBoxDialogObject *obj, PyObject* args)
{
    if(obj->d)
    {
	PyObject* cb = NULL;
	if (!PyArg_ParseTuple(args, "O", &cb))
	    return NULL;

	if (cb && !PyCallable_Check(cb)) {
	    PyErr_SetString(PyExc_TypeError, "callable expected");
	    return NULL;
	}
	obj->d->SetExitCallback(cb);
    }
    Py_INCREF(Py_None);
    return Py_None;	
}

static PyObject* ListBoxDialog_setMenuItems(ListBoxDialogObject *obj, PyObject* args)
{
    TInt error = KErrNone;
    if(obj->d)
    {
	PyObject* items = NULL;
	if (!PyArg_ParseTuple(args, "O!", &PyList_Type, &items))
		return NULL;
	if (PyList_Size(items) > 0)
	    obj->d->SetMenuItems(items);
	else
	{
	    obj->d->UnSetMenuItems();
	}
    }

    RETURN_ERROR_OR_PYNONE(error);	
}

static PyObject* ListBoxDialog_setSoftKeyVisible(ListBoxDialogObject *obj, PyObject* args)
{
    if(obj->d)
    {
	int visible = 0;
	int btnId = -1;
	if (!PyArg_ParseTuple(args, "ii", &btnId, &visible))
		return NULL;

	obj->d->SetSoftKeyVisible(btnId, visible==1);
    }

    Py_INCREF(Py_None);   
    return Py_None;

}

static PyObject* ListBoxDialog_setItems(ListBoxDialogObject *obj, PyObject* args)
{
    TInt error = KErrNone;
    if(obj->d)
    {
	PyObject* list;
	int current = -1;
	if (!PyArg_ParseTuple(args, "O!|i", &PyList_Type, &list, &current))
		return NULL;

	CEikListBox* listBox = obj->d->GetListBox();
	CTextListBoxModel* model = (CTextListBoxModel*)listBox->Model();
	CDesCArray* items_list = static_cast< CDesCArray* > (model->ItemTextArray());
	listBox->Reset();
	items_list->Reset();
	if(obj->lb_icons != NULL)
	    obj->lb_icons->Reset();

	error = create_listbox_items(obj->lb_type, list, items_list, NULL, obj->lb_icons);
	RETURN_IF_ERROR(error);
	if (current >= 0 && current <= items_list->Count())
	{
	    listBox->SetCurrentItemIndex(current);
	}

	TRAP(error, {
		listBox->HandleItemAdditionL();
		listBox->UpdateScrollBarsL();
	});
    }

    RETURN_ERROR_OR_PYNONE(error);	
}

static PyObject* ListBoxDialog_addItems(ListBoxDialogObject *obj, PyObject* args)
{
    TInt error = KErrNone;
    if(obj->d)
    {
	PyObject* list;
	if (!PyArg_ParseTuple(args, "O!|i", &PyList_Type, &list))
		return NULL;

	CEikListBox* listBox = obj->d->GetListBox();
	CTextListBoxModel* model = (CTextListBoxModel*)listBox->Model();
	CDesCArray* items_list = static_cast< CDesCArray* > ( model->ItemTextArray() );
	if (error == KErrNone)
	    error = create_listbox_items(obj->lb_type, list, items_list, NULL, obj->lb_icons);
	    RETURN_IF_ERROR(error);

	TRAP(error, {
		listBox->HandleItemAdditionL();
		listBox->UpdateScrollBarsL();
	});
    }

    RETURN_ERROR_OR_PYNONE(error);	
}


static PyObject* ListBoxDialog_clearItems(ListBoxDialogObject *obj, PyObject* args)
{
    TInt error = KErrNone;
    if(obj->d)
    {
	CEikListBox* listBox = obj->d->GetListBox();
	CTextListBoxModel* model = (CTextListBoxModel*)listBox->Model();
	CDesCArray* itemsArray = static_cast< CDesCArray* > ( model->ItemTextArray() );
	listBox->Reset();
	itemsArray->Reset();
	if(obj->lb_icons != NULL)
	    obj->lb_icons->Reset();

	TRAP(error, {
		listBox->HandleItemRemovalL();
		listBox->UpdateScrollBarsL();
	});
    }

    RETURN_ERROR_OR_PYNONE(error);	
}

static PyObject* ListBoxDialog_removeItem(ListBoxDialogObject *obj, PyObject* args)
{
    TInt error = KErrNone;
    if(obj->d)
    {
	int idx = -1; 
	if (!PyArg_ParseTuple(args, "i", &idx))
	    return NULL;
	
	CEikListBox* listBox = obj->d->GetListBox();
	CTextListBoxModel* model = (CTextListBoxModel*)listBox->Model();
	CDesCArray* itemsArray = static_cast< CDesCArray* > ( model->ItemTextArray() );
	TInt items_count = model->NumberOfItems();
	if(idx >= 0 && idx <= items_count)
	{
	    itemsArray->Delete(idx);
	    if(obj->lb_icons)
		obj->lb_icons->Delete(idx);
	}
	TRAP(error, {
		listBox->HandleItemRemovalL();
		listBox->UpdateScrollBarsL();
	});    
    }

    RETURN_ERROR_OR_PYNONE(error);	
}



static PyObject* ListBoxDialog_setFocusedItem(ListBoxDialogObject *obj, PyObject* args)
{
    TInt error = KErrNone;
    if(obj->d)
    {
	int current = 0;
	if (!PyArg_ParseTuple(args, "i", &current))
		return NULL;

	CEikListBox* listBox = obj->d->GetListBox();
	CTextListBoxModel* model = (CTextListBoxModel*)listBox->Model();
	CDesCArray* items_list = static_cast< CDesCArray* > ( model->ItemTextArray() );
	if ((current >= 0) && (current <= items_list->Count()))
	{
	    listBox->SetCurrentItemIndex(current);
	}
	TRAP(error, {
		listBox->UpdateScrollBarsL();
	});
    }

    RETURN_ERROR_OR_PYNONE(error);	
}



static PyObject* ListBoxDialog_current(ListBoxDialogObject *obj, PyObject* args)
{
    TInt idx = -1;
    if(obj->d)
    {
	idx = obj->d->GetListBox()->CurrentItemIndex();
    }
    return Py_BuildValue("i", idx);	
}

static PyObject* ListBoxDialog_enableMarquee(ListBoxDialogObject *obj, PyObject* args)
{
    TInt error = KErrNone;
    if(obj->d)
    {
	int enable = 1; 
	if (!PyArg_ParseTuple(args, "|i", &enable))
	    return NULL;
	
	TRAP(error, obj->d->EnableMarqueeL(enable==1, obj->lb_type));
    }

    RETURN_ERROR_OR_PYNONE(error);	
}


static PyObject* ListBoxDialog_showFindPopup(ListBoxDialogObject *obj, PyObject* args)
{
    if(obj->d)
    {
	obj->d->EnableSearchFieldL(ETrue);
    }
    Py_INCREF(Py_None);
    return Py_None;	
}

static PyObject* ListBoxDialog_finish(ListBoxDialogObject *obj, PyObject* args)
{
    TInt error = KErrNone;
    if(obj->d)
    {
	TRAP(error, obj->d->FinishL());
    }

    RETURN_ERROR_OR_PYNONE(error);	
}



const static PyMethodDef listboxdialog_methods[] = 
{
    {"show", (PyCFunction)ListBoxDialog_show, METH_NOARGS},
    {"setTitle", (PyCFunction)ListBoxDialog_setTitle, METH_VARARGS},
    {"setMenuCallbacks", (PyCFunction)ListBoxDialog_setMenuCallbacks, METH_VARARGS},
    {"setKeyEventsCallback", (PyCFunction)ListBoxDialog_setKeyEventsCallbacks, METH_VARARGS},
    {"setExitCallback", (PyCFunction)ListBoxDialog_setExitCallbacks, METH_VARARGS},
    {"setMenuItems", (PyCFunction)ListBoxDialog_setMenuItems, METH_VARARGS},
    {"setSoftKeyVisible", (PyCFunction)ListBoxDialog_setSoftKeyVisible, METH_VARARGS},
    {"setItems", (PyCFunction)ListBoxDialog_setItems, METH_VARARGS},
    {"addItems", (PyCFunction)ListBoxDialog_addItems, METH_VARARGS},
    {"clearItems", (PyCFunction)ListBoxDialog_clearItems, METH_NOARGS},
    {"removeItem", (PyCFunction)ListBoxDialog_removeItem, METH_VARARGS},
    {"setFocusedItem", (PyCFunction)ListBoxDialog_setFocusedItem, METH_VARARGS},
    {"current", (PyCFunction)ListBoxDialog_current, METH_NOARGS},
    {"enableMarquee", (PyCFunction)ListBoxDialog_enableMarquee, METH_VARARGS},  
    {"showFindPopup", (PyCFunction)ListBoxDialog_showFindPopup, METH_VARARGS},
    {"finish", (PyCFunction)ListBoxDialog_finish, METH_NOARGS},
    {NULL, NULL}
};

void ListBoxDialog_dealloc(ListBoxDialogObject *obj)
{
    PyObject_Del(obj);
}


PyObject * ListBoxDialog_getattr(ListBoxDialogObject* obj, char *name)
{
    return Py_FindMethod((PyMethodDef*)listboxdialog_methods, (PyObject*)obj, name);
}


int ListBoxDialog_setattr(ListBoxDialogObject*  obj, char *name, PyObject *v)
{
    return 0;
}


