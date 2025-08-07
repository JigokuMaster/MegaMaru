/* Copyright (c) 2008 - 2009 Nokia Corporation
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */


//#include <stdlib.h>
//#include <string.h>
#include <aknapp.h>
#include <eikstart.h>
#include <AknDoc.h>
#include <aknglobalnote.h>
#include <eiknotapi.h>
#include <e32base.h>
#include <e32std.h>


_LIT(KUiDLL, "kf_Python_appui.dll");

_LIT(KErrorMessage, "Check if the following components are installed.\n->Python Runtime\n->PIPS Library");

static TUid KUidPythonApp = KNullUid;   // Real UID is set in E32Main()

RLibrary appuiDllHandle;

class CPythonDocument : public CAknDocument
{
public:
	CPythonDocument(CEikApplication& aApp);
	~CPythonDocument();
private:
	CEikAppUi* CreateAppUiL();

};

class CPythonApplication : public CAknApplication
{
private:
	CApaDocument* CreateDocumentL();
	TUid AppDllUid() const;
	
};



CPythonDocument::CPythonDocument(CEikApplication& aApp) :
    CAknDocument(aApp)
{
}
void ShowErrorAndExit(TInt errno)
{
    TAknGlobalNoteType noteType = EAknGlobalErrorNote;
    CAknGlobalNote *dialog = NULL;

    TRAPD(err,
            {
                dialog = CAknGlobalNote::NewL();
                CleanupStack::PushL(dialog);
                dialog->ShowNoteL(noteType, KErrorMessage);
                CleanupStack::PopAndDestroy(dialog);
            });

    User::Exit(errno);
}




CEikAppUi* CPythonDocument::CreateAppUiL()
{

    TFileName uiDLL;
    uiDLL = KUiDLL;

    TInt err = appuiDllHandle.Load(uiDLL);
    if (err != KErrNone)
    {
        ShowErrorAndExit(err);
    }

    TLibraryFunction uiEntryFunction = appuiDllHandle.Lookup(1);
    CEikAppUi* eikAppUi = (CEikAppUi*) uiEntryFunction();
    return eikAppUi;
}

CPythonDocument::~CPythonDocument()
{
    appuiDllHandle.Close();
}

TUid CPythonApplication::AppDllUid() const
{
    return KUidPythonApp;
}

CApaDocument* CPythonApplication::CreateDocumentL()
{
    return new (ELeave) CPythonDocument(*this);
}

EXPORT_C CApaApplication* NewApplication()
{

    return new CPythonApplication;
}


GLDEF_C TInt E32Main()
{

    // Set application UID from Process' Secure ID.
    KUidPythonApp.iUid = RProcess().SecureId();
    return EikStart::RunApplication(NewApplication);
}



