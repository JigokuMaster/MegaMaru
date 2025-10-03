#ifndef __LISTBOX_H
#define __LISTBOX_H

#include "appuifw_utils.h"

class CListBoxDialog;

struct ListBoxDialogObject;

struct ListBoxDialogObject {
  PyObject_VAR_HEAD
  CListBoxDialog* d;
  ListboxType lb_type;
  TInt d_executed;
  CArrayPtrFlat<CGulIcon>* lb_icons;
};


PyObject* ListBoxDialog_create(PyObject* /*self*/, PyObject *args);

void ListBoxDialog_dealloc(ListBoxDialogObject *obj);

PyObject * ListBoxDialog_getattr(ListBoxDialogObject* obj, char *name);

int ListBoxDialog_setattr(ListBoxDialogObject*  obj, char *name, PyObject *v);

#endif // __LISTBOX_H

