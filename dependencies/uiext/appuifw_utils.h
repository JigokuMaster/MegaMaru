#ifndef __APPUIFWUTILS_H
#define __APPUIFWUTILS_H

#include <aknlists.h>
#include <gulicon.h>
#include <gulalign.h>
#include <Python.h>
#include <symbian_python_ext_util.h>

enum ListboxType {ESingleListbox, EDoubleListbox, ESingleGraphicListbox, EDoubleGraphicListbox };

struct icon_data {
  TBuf<KMaxFileName> ob_file;
  int ob_bmpId;
  int ob_maskId;
};

struct Icon_object {
  PyObject_VAR_HEAD
  icon_data* icon;
};

_LIT(KSeparatorTab, "\t");
_LIT(KEmptyString, "");

TInt create_listbox_items(ListboxType lb_type,
                                     PyObject* list,
                                     CDesCArray*& items_list,
                                     TBool is_popup_style = EFalse,
                     CArrayPtr<CGulIcon>* icons = NULL);

#endif // __APPUIFWUTILS_H
