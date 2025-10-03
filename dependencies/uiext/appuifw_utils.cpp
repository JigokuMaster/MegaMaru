#include "appuifw_utils.h"

/* An internal helper function */
PyObject *RemoveTabs(PyObject *unicodeString )
{
  _LIT(KEmpty, " ");

  TBuf<(KMaxFileName)> temp;

  temp.Append(PyUnicode_AsUnicode(unicodeString),
                    Min(PyUnicode_GetSize(unicodeString), KMaxFileName));

  TInt res = KErrNotFound;
  res = temp.Find(KSeparatorTab);
  while (res!=KErrNotFound)
  {
    res = temp.Find(KSeparatorTab);
    if ((res != KErrNotFound) ) {
      temp.Replace(res, 1, KEmpty );
    }
  }
  PyObject *newUnicodeObject = Py_BuildValue("u#", temp.Ptr(), temp.Length());

  return newUnicodeObject;
}

/* An internal helper function */
TInt create_listbox_items(ListboxType lb_type,
                                     PyObject* list,
                                     CDesCArray*& items_list,
                                     TBool is_popup_style,
				     CArrayPtr<CGulIcon>* icons)
{

  Icon_object *io = NULL;
  TBool items_list_borrowed = ETrue;

  if (!items_list) {
    if (!(items_list = new CDesCArrayFlat(5)))
      return KErrNoMemory;
    else
      items_list_borrowed = EFalse;
  }

  TInt error = KErrNone;
  TBuf<((KMaxFileName+1)*2)> temp;
  int sz = PyList_Size(list);

  CEikonEnv* env = CEikonEnv::Static();

  for (int i = 0; i < sz; i++) {
    if (lb_type == ESingleListbox) {
      PyObject* s = PyList_GetItem(list, i);
      if (!PyUnicode_Check(s))
        error = KErrArgument;
      else {
        if (is_popup_style) {
          temp.Copy(KEmptyString);
        }
        else {
          temp.Copy(KSeparatorTab);
        }
        temp.Append(PyUnicode_AsUnicode(RemoveTabs(s)),
                    Min(PyUnicode_GetSize(s), KMaxFileName));
      }
    }
    else if (lb_type == EDoubleListbox) {
      PyObject* t = PyList_GetItem(list, i);
      if (!PyTuple_Check(t))
        error = KErrArgument;
      else {
        PyObject* s1 = PyTuple_GetItem(t, 0);
        PyObject* s2 = PyTuple_GetItem(t, 1);
        if ((!PyUnicode_Check(s1)) || (!PyUnicode_Check(s2))) {
          error = KErrArgument;
        }
        else {
          if (is_popup_style) {
            temp.Copy(KEmptyString);
          }
          else {
            temp.Copy(KSeparatorTab);
          }

          temp.Append(PyUnicode_AsUnicode(RemoveTabs(s1)),
                      Min(PyUnicode_GetSize(s1), KMaxFileName));
          temp.Append(KSeparatorTab);
          temp.Append(PyUnicode_AsUnicode(RemoveTabs(s2)),
                      Min(PyUnicode_GetSize(s2), KMaxFileName));

        }
      }
    }

    else if (lb_type == ESingleGraphicListbox) {
      PyObject* t = PyList_GetItem(list, i);
      if (!PyTuple_Check(t)) {
        error = KErrArgument;
      }
      else {
        PyObject* s1; // = PyTuple_GetItem(t, 0);
        if (!PyArg_ParseTuple(t, "OO", &s1, &io)) {
          error = KErrArgument;
        }
        //if (!PyArg_ParseTuple(t, "OO!", &s1, &Icon_type, &io)) {
        //  error = KErrArgument;
        //}
        else {
          if (is_popup_style) {
            temp.Copy(KEmptyString);
          }
          else {
            temp.Copy(KEmptyString);
            temp.AppendNum(i);
            temp.Append(KSeparatorTab);
           }
        temp.Append(PyUnicode_AsUnicode(RemoveTabs(s1)), Min(PyUnicode_GetSize(s1), KMaxFileName));
        }

        // error in argument:
        if (error != KErrNone) {
          SPyErr_SetFromSymbianOSErr(error);
          delete items_list;
          items_list = NULL;
          return error;
        }

        CGulIcon* iIcon = NULL;

#if SERIES60_VERSION>=28
        CFbsBitmap* bitMap = NULL;
        CFbsBitmap* mask = NULL;

        TRAP(error, {
        AknIconUtils::CreateIconL(bitMap, mask, io->icon->ob_file, io->icon->ob_bmpId, io->icon->ob_maskId);
        iIcon = CGulIcon::NewL(bitMap, mask);
        });
#else
        TRAP(error,
        iIcon = env->CreateIconL(io->icon->ob_file, io->icon->ob_bmpId, io->icon->ob_maskId) );
#endif /* SERIES60_VERSION */
        if (error != KErrNone) {
          SPyErr_SetFromSymbianOSErr(error);
          delete items_list;
          items_list = NULL;
          return error;
        }
        TRAP(error, icons->AppendL(iIcon) );
        if (error != KErrNone) {
          SPyErr_SetFromSymbianOSErr(error);
          delete items_list;
          items_list = NULL;
          return error;
        }

      }
    }
    else if (lb_type == EDoubleGraphicListbox) {
      PyObject* t = PyList_GetItem(list, i);
      if (!PyTuple_Check(t)) {
        error = KErrArgument;
      }
      else {
        PyObject* s1; // = PyTuple_GetItem(t, 0);
        PyObject* s2; // = PyTuple_GetItem(t, 1);

        /*if (!PyArg_ParseTuple(t, "OOO!", &s1, &s2, &Icon_type, &io)) {
          error = KErrArgument;
        }*/
	if (!PyArg_ParseTuple(t, "OOO", &s1, &s2, &io)) {
          error = KErrArgument;
        }

        else {
          if (is_popup_style) {
            temp.Copy(KEmptyString);
          }
          else {
            temp.Copy(KEmptyString);
            temp.AppendNum(i);
            temp.Append(KSeparatorTab);
          }
          temp.Append(PyUnicode_AsUnicode(RemoveTabs(s1)), Min(PyUnicode_GetSize(s1), KMaxFileName));
          temp.Append(KSeparatorTab);
          temp.Append(PyUnicode_AsUnicode(RemoveTabs(s2)), Min(PyUnicode_GetSize(s2), KMaxFileName));

        }

        // error in argument:
        if (error != KErrNone) {
          SPyErr_SetFromSymbianOSErr(error);
          delete items_list;
          items_list = NULL;
          return error;
        }

        CGulIcon* iIcon = NULL;

#if SERIES60_VERSION>=28
        CFbsBitmap* bitMap = NULL;
        CFbsBitmap* mask = NULL;

        TRAP(error, { AknIconUtils::CreateIconL(
        bitMap, mask, io->icon->ob_file, io->icon->ob_bmpId, io->icon->ob_maskId);
        iIcon = CGulIcon::NewL(bitMap, mask);
        });
#else
        TRAP(error,
        iIcon = env->CreateIconL(io->icon->ob_file, io->icon->ob_bmpId, io->icon->ob_maskId) );
#endif /* SERIES60_VERSION */
        if (error != KErrNone) {
          SPyErr_SetFromSymbianOSErr(error);
          delete items_list;
          items_list = NULL;
          return error;
        }

        TRAP(error, icons->AppendL(iIcon) );
        if (error != KErrNone) {
          SPyErr_SetFromSymbianOSErr(error);
          delete items_list;
          items_list = NULL;
          return error;
        }
      }
    }

    if (error == KErrNone) {
      TRAP(error, items_list->AppendL(temp));
    }

    if ((error != KErrNone) && (!items_list_borrowed)) {
      delete items_list;
      items_list = NULL;
      break;
    }
  }

  return error;
}

