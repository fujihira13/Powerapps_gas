"""Generate the approved management screen and targeted integration locally.

The output is a candidate, not an editor upload or a saved app.
"""
import copy
import json
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"outputs/environment-management-20261003/implementation/baseline/canvas"
OUT=BASE.parent.parent/"candidate/canvas"
FLOW="'架空ログ証跡_環境サーバー管理'"
NAVY="RGBA(25, 54, 92, 1)"; BLUE="RGBA(15, 108, 189, 1)"
WHITE="RGBA(255, 255, 255, 1)"; EDGE="RGBA(208, 220, 234, 1)"

def control(name,kind,props,children=None,variant=None):
    value={"Control":kind}
    if variant:value["Variant"]=variant
    value["Properties"]={k:v if str(v).startswith("=") else "="+str(v) for k,v in props.items()}
    if children:value["Children"]=children
    return {name:value}

def label(name,text,x,y,w,h=32,**more):
    return control(name,"Label",dict(dict(Text=text,X=x,Y=y,Width=w,Height=h,Color=NAVY,Font="Font.'Segoe UI'",Size=14),**more))

def button(name,text,x,y,w,action,primary=False,**more):
    return control(name,"Classic/Button",dict(dict(Text=text,Tooltip=text,X=x,Y=y,Width=w,Height=42,
        OnSelect=action,DisplayMode="If(varM05Busy || varM05Unknown || !varM05Ready, DisplayMode.Disabled, DisplayMode.Edit)",
        Fill=BLUE if primary else WHITE,Color=WHITE if primary else NAVY,BorderColor=BLUE if primary else EDGE,
        BorderThickness=1,HoverFill=BLUE,HoverColor=WHITE,PressedFill="RGBA(9, 82, 144, 1)",PressedColor=WHITE,
        Font="Font.'Segoe UI'",Size=12,RadiusTopLeft=4,RadiusTopRight=4,RadiusBottomLeft=4,RadiusBottomRight=4),**more))

READBACK='''Set(varM05Parsed, ParseJSON(varM05Reply.result));
If(Boolean(varM05Parsed.ok),
  ClearCollect(colM05Rows, ForAll(Table(varM05Parsed.rows) As saved, {
    Id: Text(saved.Value.id), Version: Text(saved.Value.version),
    Env: Text(saved.Value.environment), Server: Text(saved.Value.server),
    EnvEnabled: Boolean(saved.Value.environmentEnabled), ServerEnabled: Boolean(saved.Value.serverEnabled)
  }));
  Set(varM05Unknown, false);
  Set(varM05Error, "");
  Set(varM05Dialog, "");
  If(varM05Op = "renameEnvironment" || varM05Op = "addEnvironment", Set(varM05Env, varM05NewEnv));
  If(IsBlank(LookUp(colM05Rows, Env = varM05Env)), Set(varM05Env, First(Filter(colM05Rows, EnvEnabled)).Env));
  Set(varM05Ready, true),
  Set(varM05Error, Text(varM05Parsed.reason));
  If("読み直して" in varM05Error, Set(varM05Unknown, true))
)'''

def begin(op,target="Blank()",env="varM05Env",server='""',dialog='"edit"'):
    scope="colM05Rows" if op=="addEnvironment" else "Filter(colM05Rows, Env = varM05OldEnv)"
    return f'''If(!varM05Busy && !varM05Unknown,
Set(varM05Op, "{op}"); Set(varM05Target, {target});
Set(varM05OldEnv, {env}); Set(varM05OldServer, {server});
Set(varM05NewEnv, varM05OldEnv); Set(varM05NewServer, varM05OldServer);
Set(varM05Expected, ForAll({scope} As proof, {{id: proof.Id, version: proof.Version}}));
Set(varM05Error, ""); Set(varM05Dialog, {dialog});
Reset(txtM05Env); Reset(txtM05Server)
)'''

def manage_screen():
    envItems="SortByColumns(DropColumns(GroupBy(Filter(colM05Rows, EnvEnabled = varM05EnvActive), Env, Members), Members), \"Env\", SortOrder.Ascending)"
    srvItems="SortByColumns(Filter(colM05Rows, Env = varM05Env && ServerEnabled = varM05ServerActive), \"Server\", SortOrder.Ascending)"
    def panel(server=False):
        prefix="srv" if server else "env"; panelName=prefix+"M05Panel"; gallery=prefix+"M05List"
        nameProp="Server" if server else "Env"
        filterExpr=srvItems if server else envItems
        # Generous measured character width lets 100-character values wrap.
        nameWidth="Parent.TemplateWidth - 28" if server else "Max(80, Parent.TemplateWidth - 190)"
        name=label(prefix+"M05Name","ThisItem."+nameProp,14,14,nameWidth,
            "Max(36, RoundUp(Len(ThisItem."+nameProp+") * 18 / Max(1, Self.Width), 0) * 26)",FontWeight="FontWeight.Semibold")
        nameControl=prefix+"M05Name"
        rowbuttons=[]
        if not server:
            rowbuttons.append(button("btnM05ViewServers",'"サーバーを見る"',"Parent.TemplateWidth - 162",14,148,
                'Set(varM05Env, ThisItem.Env); Set(varM05ServerActive, true)'))
        env="ThisItem.Env"; target="ThisItem.Id" if server else "First(Filter(colM05Rows, Env = ThisItem.Env)).Id"
        srv="ThisItem.Server" if server else '""'
        rowbuttons.append(button(prefix+"M05Rename",'"名称を変更"',14,nameControl+".Y + "+nameControl+".Height + 12",116,
            begin("renameServer" if server else "renameEnvironment",target,env,srv)))
        op='If(ThisItem.ServerEnabled, "endServer", "reactivateServer")' if server else 'If(varM05EnvActive, "endEnvironment", "reactivateEnvironment")'
        state='ThisItem.ServerEnabled' if server else 'varM05EnvActive'
        action=begin("endServer" if server else "endEnvironment",target,env,srv,dialog='"confirm"').replace('Set(varM05Op, "'+("endServer" if server else "endEnvironment")+'");','Set(varM05Op, '+op+');')
        rowbuttons.append(button(prefix+"M05Toggle",f'If({state}, "使用を終了", "再び使用する")',
            "If(Parent.TemplateWidth < 310, 14, 142)",nameControl+".Y + "+nameControl+".Height + If(Parent.TemplateWidth < 310, 66, 12)",144,action,
            **({"DisplayMode":"If(varM05Busy || varM05Unknown || (!ThisItem.ServerEnabled && !Coalesce(LookUp(colM05Rows, Env = varM05Env).EnvEnabled, false)), DisplayMode.Disabled, DisplayMode.Edit)"} if server else {})))
        card=control(prefix+"M05Card","Rectangle",{"Fill":WHITE,"BorderColor":EDGE,"BorderThickness":1,"Width":"Parent.TemplateWidth - 2","Height":prefix+"M05Toggle.Y + 56","X":0,"Y":0})
        template="Max(128, RoundUp(Max(1, Max("+filterExpr+", Len("+nameProp+"))) * 18 / Max(80, Self.Width - "+("28" if server else "190")+"), 0) * 26 + If(Self.Width < 310, 136, 82))"
        count="CountRows("+filterExpr+")"
        gal=control(gallery,"Gallery",{"Items":filterExpr,"Selectable":"false","AccessibleLabel":'"'+("サーバー一覧" if server else "環境一覧")+'"',"X":18,"Y":190 if server else 132,"Width":"Parent.Width - 36","TemplatePadding":12,"TemplateSize":template,
            "Height":f"Max(48, {count} * (Self.TemplateHeight + Self.TemplatePadding) + Self.TemplatePadding)","ShowScrollbar":"false","DelayItemLoading":"false"},[card,name]+rowbuttons,variant="Vertical")
        title=label(prefix+"M05Title",'"'+("サーバー" if server else "環境")+'"',18,18,"Parent.Width - 180",42,Size=20,FontWeight="FontWeight.Bold")
        activeVar="varM05ServerActive" if server else "varM05EnvActive"
        addaction=begin("addServer" if server else "addEnvironment","First(Filter(colM05Rows, Env = varM05Env)).Id" if server else "Blank()", "varM05Env" if server else '""')
        add=button(prefix+"M05Add",'"'+("サーバーを追加" if server else "環境を追加")+'"',"Parent.Width - 168",18,150,addaction,True,
            **({"DisplayMode":"If(varM05Busy || varM05Unknown || !Coalesce(LookUp(colM05Rows, Env = varM05Env).EnvEnabled, false), DisplayMode.Disabled, DisplayMode.Edit)"} if server else {"DisplayMode":"If(varM05Busy || varM05Unknown || !varM05Ready, DisplayMode.Disabled, DisplayMode.Edit)"}))
        tabY=132 if server else 74
        t1=button(prefix+"M05TabActive",'"使用中の'+("サーバー" if server else "環境")+'"',18,tabY,132 if not server else 148,"Set("+activeVar+", true)",Fill=f"If({activeVar}, RGBA(232, 242, 253, 1), {WHITE})",FontWeight=f"If({activeVar}, FontWeight.Semibold, FontWeight.Normal)")
        t2=button(prefix+"M05TabEnded",'"使用終了した'+("サーバー" if server else "環境")+'"',162 if not server else 178,tabY,164 if not server else 180,"Set("+activeVar+", false)",Fill=f"If(!{activeVar}, RGBA(232, 242, 253, 1), {WHITE})",FontWeight=f"If(!{activeVar}, FontWeight.Semibold, FontWeight.Normal)")
        # At mobile widths the two tab buttons stack, preserving touch targets.
        t2[prefix+"M05TabEnded"]["Properties"].update({"X":"=If(Parent.Width < 390, 18, "+str(178 if server else 162)+")","Y":"="+str(tabY)+" + If(Parent.Width < 390, 48, 0)"})
        gal[gallery]["Properties"]["Y"]="="+str(190 if server else 132)+" + If(Parent.Width < 390, 48, 0)"
        children=[title,add]
        if server:
            children.append(label("lblM05EnvContext",'"選択した環境：" & Coalesce(varM05Env, "")',18,72,"Parent.Width - 36",48,AutoHeight="true",FontWeight="FontWeight.Semibold"))
            # The context may wrap; all following elements use its actual height.
            delta="Max(0, lblM05EnvContext.Height - 48)"
            for obj in (t1,t2,gal):
                item=next(iter(obj.values()));item["Properties"]["Y"]+=" + "+delta
        children += [t1,t2,gal,label(prefix+"M05Empty",'"'+("該当するサーバーはありません。" if server else "該当する環境はありません。")+'"',18,gallery+".Y","Parent.Width - 36",48,Visible=count+" = 0")]
        return control(panelName,"GroupContainer",{"DropShadow":"DropShadow.None","Fill":WHITE,"BorderColor":EDGE,"BorderThickness":1,
            "X":"If(Parent.Width > 760, (Parent.Width + 24) / 2, 0)" if server else 0,
            "Y":"If(Parent.Width > 760, 0, envM05Panel.Height + 24)" if server else 0,
            "Width":"If(Parent.Width > 760, (Parent.Width - 24) / 2, Parent.Width)","Height":gallery+".Y + "+gallery+".Height + 18"},children,variant="ManualLayout")

    reload='''If(!varM05Busy,
Set(varM05Busy, true); Set(varM05Error, ""); Set(varM05Op, "list");
IfError(Set(varM05Reply, FLOW.Run(JSON({operation: "list"}, JSONFormat.Compact)));
READBACK,
Set(varM05Error, "登録内容を読み取れません。読み直してから操作してください。"); Set(varM05Unknown, true));
Set(varM05Busy, false))'''.replace("FLOW",FLOW).replace("READBACK",READBACK)
    commit='''If(!varM05Busy && !varM05Unknown,
Set(varM05Busy, true); Set(varM05Error, "");
IfError(Set(varM05Reply, FLOW.Run(JSON({operation: varM05Op, targetId: Coalesce(varM05Target, ""),
 expectedRows: varM05Expected, environment: varM05NewEnv, server: varM05NewServer}, JSONFormat.Compact)));
READBACK,
Set(varM05Error, "保存結果を確認できません。読み直してから登録内容を確認してください。"); Set(varM05Unknown, true));
Set(varM05Busy, false))'''.replace("FLOW",FLOW).replace("READBACK",READBACK)
    validate='''Set(varM05NewEnv, Trim(txtM05Env.Text)); Set(varM05NewServer, Trim(txtM05Server.Text));
Set(varM05Error,
If((varM05Op = "addEnvironment" || varM05Op = "renameEnvironment") && IsBlank(varM05NewEnv), "環境名を入力してください。",
(varM05Op = "addEnvironment" || varM05Op = "renameEnvironment") && Len(varM05NewEnv) > 100, "環境名は100文字以内で入力してください。",
(varM05Op = "addEnvironment" || varM05Op = "renameEnvironment") && CountIf(colM05Rows, Lower(Trim(Env)) = Lower(varM05NewEnv) && (varM05Op = "addEnvironment" || Env <> varM05OldEnv)) > 0, "同じ環境名が登録されています。",
(varM05Op = "addEnvironment" || varM05Op = "addServer" || varM05Op = "renameServer") && IsBlank(varM05NewServer), "サーバー名を入力してください。",
Len(varM05NewServer) > 100, "サーバー名は100文字以内で入力してください。",
(varM05Op = "addServer" || varM05Op = "renameServer") && CountIf(colM05Rows, Env = varM05OldEnv && Lower(Trim(Server)) = Lower(varM05NewServer) && (varM05Op = "addServer" || Id <> varM05Target)) > 0, "この環境に同じサーバー名が登録されています。", ""));
If(IsBlank(varM05Error), If(varM05Op = "renameEnvironment" || varM05Op = "renameServer", Set(varM05Dialog, "confirm"), Select(btnM05Commit)))'''
    bodyChildren=[button("btnM05Back",'"進捗一覧に戻る"',0,18,192,'Navigate(Screen2, ScreenTransition.None)',Height=36),
        label("lblM05Title",'"環境・サーバーの管理"',0,70,"Parent.Width",52,Size="If(Parent.Width < 450, 20, 24)",FontWeight="FontWeight.Bold"),
        label("lblM05Error","varM05Error",0,126,"Parent.Width",48,AutoHeight="true",Visible='!IsBlank(varM05Error) && IsBlank(varM05Dialog)',Color="RGBA(163, 38, 45, 1)"),
        button("btnM05Reload",'"読み直す"',0,"lblM05Error.Y + lblM05Error.Height + 6",120,reload,Visible='!IsBlank(varM05Error) && IsBlank(varM05Dialog)',DisplayMode="If(varM05Busy, DisplayMode.Disabled, DisplayMode.Edit)")]
    panels=control("pnlM05Lists","GroupContainer",{"DropShadow":"DropShadow.None","X":0,"Y":"If(lblM05Error.Visible, btnM05Reload.Y + 58, 132)","Width":"Parent.Width","Height":"If(Self.Width > 760, Max(envM05Panel.Height, srvM05Panel.Height), envM05Panel.Height + srvM05Panel.Height + 24)"},[panel(),panel(True)],variant="ManualLayout")
    bodyChildren.append(panels)
    root=control("conM05Scroll","GroupContainer",{"Height":"Parent.Height","Width":"Parent.Width","LayoutDirection":"LayoutDirection.Vertical","LayoutOverflowY":"LayoutOverflow.Scroll","DropShadow":"DropShadow.None"},[
        control("conM05Center","GroupContainer",{"AlignInContainer":"AlignInContainer.Center","FillPortions":0,"LayoutMinHeight":0,"LayoutMinWidth":0,"Width":"Min(Parent.Width - 48, 1200)","Height":"Max(Parent.Height, pnlM05Lists.Y + pnlM05Lists.Height + 24)","DropShadow":"DropShadow.None"},bodyChildren,variant="ManualLayout")],variant="AutoLayout")
    editTitle='Switch(varM05Op, "addEnvironment", "環境を追加", "addServer", "サーバーを追加", "renameEnvironment", "環境名を変更", "renameServer", "サーバー名を変更", "確認")'
    confirmTitle='Switch(varM05Op, "renameEnvironment", "環境名を「" & varM05OldEnv & "」から「" & varM05NewEnv & "」に変更しますか？", "renameServer", "サーバー名を「" & varM05OldServer & "」から「" & varM05NewServer & "」に変更しますか？", "確認")'
    confirmBody='Switch(varM05Op, "renameEnvironment", "ログに書かれている環境名も「" & varM05NewEnv & "」になっていることを確認してください。", "renameServer", "ログに書かれているサーバー名も「" & varM05NewServer & "」になっていることを確認してください。", "endEnvironment", varM05OldEnv & "を使用終了にしますか？ この環境のサーバーは使用できなくなります。", "endServer", varM05OldServer & "を使用終了にしますか？ 使用できなくなります。", "reactivateEnvironment", varM05OldEnv & "を再び使用しますか？", "reactivateServer", varM05OldServer & "を再び使用しますか？", "")'
    envVisible='varM05Op = "addEnvironment" || varM05Op = "renameEnvironment"'
    srvVisible='varM05Op = "addEnvironment" || varM05Op = "addServer" || varM05Op = "renameServer"'
    modalChildren=[label("lblM05DialogTitle",'If(varM05Dialog = "edit", '+editTitle+", "+confirmTitle+")",24,18,"Parent.Width - 48",52,AutoHeight="true",Size=18,FontWeight="FontWeight.Bold"),
        label("lblM05EnvInput",'"環境名"',24,"lblM05DialogTitle.Y + lblM05DialogTitle.Height + 16","Parent.Width - 48",30,Visible=f'varM05Dialog = "edit" && ({envVisible})'),
        control("txtM05Env","Classic/TextInput",{"Default":"Coalesce(varM05OldEnv, \"\")","AccessibleLabel":'"環境名"',"X":24,"Y":"lblM05EnvInput.Y + 34","Width":"Parent.Width - 48","Height":42,"MaxLength":101,"Mode":"TextMode.SingleLine","Visible":f'varM05Dialog = "edit" && ({envVisible})',"DisplayMode":"If(varM05Busy, DisplayMode.Disabled, DisplayMode.Edit)","Color":NAVY,"Fill":WHITE,"BorderColor":EDGE,"HoverBorderColor":BLUE,"FocusedBorderColor":BLUE}),
        label("lblM05ServerInput",'"サーバー名"',24,"If(txtM05Env.Visible, txtM05Env.Y + 58, lblM05DialogTitle.Y + lblM05DialogTitle.Height + 16)","Parent.Width - 48",30,Visible=f'varM05Dialog = "edit" && ({srvVisible})'),
        control("txtM05Server","Classic/TextInput",{"Default":"Coalesce(varM05OldServer, \"\")","AccessibleLabel":'"サーバー名"',"X":24,"Y":"lblM05ServerInput.Y + 34","Width":"Parent.Width - 48","Height":42,"MaxLength":101,"Mode":"TextMode.SingleLine","Visible":f'varM05Dialog = "edit" && ({srvVisible})',"DisplayMode":"If(varM05Busy, DisplayMode.Disabled, DisplayMode.Edit)","Color":NAVY,"Fill":WHITE,"BorderColor":EDGE,"HoverBorderColor":BLUE,"FocusedBorderColor":BLUE}),
        label("lblM05ConfirmBody",confirmBody,24,"lblM05DialogTitle.Y + lblM05DialogTitle.Height + 16","Parent.Width - 48",52,AutoHeight="true",Visible='varM05Dialog = "confirm"'),
        label("lblM05DialogError","varM05Error",24,"If(varM05Dialog = \"confirm\", lblM05ConfirmBody.Y + lblM05ConfirmBody.Height + 12, If(txtM05Server.Visible, txtM05Server.Y + 54, txtM05Env.Y + 54))","Parent.Width - 48",42,AutoHeight="true",Color="RGBA(163, 38, 45, 1)"),
        button("btnM05Cancel",'"キャンセル"',24,"lblM05DialogError.Y + lblM05DialogError.Height + 12",116,'Set(varM05Dialog, ""); Set(varM05Error, "")',DisplayMode="If(varM05Busy, DisplayMode.Disabled, DisplayMode.Edit)"),
        button("btnM05Continue",'If(varM05Op = "addEnvironment" || varM05Op = "addServer", "追加する", "変更を保存")',"Parent.Width - 170","btnM05Cancel.Y",146,validate,True,Visible='varM05Dialog = "edit"'),
        button("btnM05Commit",'Switch(varM05Op, "endEnvironment", "使用を終了", "endServer", "使用を終了", "reactivateEnvironment", "再び使用する", "reactivateServer", "再び使用する", "変更する")',"Parent.Width - 170","btnM05Cancel.Y",146,commit,True,Visible='varM05Dialog = "confirm"'),
        button("btnM05DialogReload",'"読み直す"',24,"btnM05Cancel.Y + 54",116,reload,Visible="varM05Unknown",DisplayMode="If(varM05Busy, DisplayMode.Disabled, DisplayMode.Edit)")]
    modal=control("conM05DialogScroll","GroupContainer",{"Visible":'!IsBlank(varM05Dialog)',"Fill":"RGBA(0, 0, 0, 0.4)","Width":"Parent.Width","Height":"Parent.Height","LayoutDirection":"LayoutDirection.Vertical","LayoutOverflowY":"LayoutOverflow.Scroll","PaddingTop":24,"PaddingBottom":24,"DropShadow":"DropShadow.None"},[
        control("conM05Dialog","GroupContainer",{"AlignInContainer":"AlignInContainer.Center","FillPortions":0,"LayoutMinHeight":0,"LayoutMinWidth":0,"DropShadow":"DropShadow.None","Fill":WHITE,"Width":"Min(Parent.Width - 32, 600)","Height":"If(varM05Unknown, btnM05DialogReload.Y + 66, btnM05Cancel.Y + 66)"},modalChildren,variant="ManualLayout")],variant="AutoLayout")
    return {"Screens":{"Screen5":{"Properties":{"Fill":"=RGBA(243, 246, 250, 1)","OnVisible":'=Set(varM05Busy, false); Set(varM05Unknown, false); Set(varM05Ready, false); Set(varM05Dialog, ""); Set(varM05Error, ""); Set(varM05EnvActive, true); Set(varM05ServerActive, true); Select(btnM05Reload)'},"Children":[root,modal]}}}

def nodes(screen):
    result={}
    def visit(items):
        for obj in items:
            for name,value in obj.items():result[name]=value;visit(value.get("Children",[]))
    visit(screen["Children"]);return result

def integrate(screens):
    s1=screens["Screen1.pa.yaml"]["Screens"]["Screen1"];n1=nodes(s1)
    active="cr6cb_isactive = '有効 (架空ログ転記先)'.有効"
    both=active+" && (cr6cb_environmentenabled = Blank() || cr6cb_environmentenabled = '環境の使用状態 (架空ログ転記先)'.使用中)"
    for obj in n1.values():
        p=obj.get("Properties",{})
        for key in ("Items","Height"):
            if key in p:p[key]=p[key].replace(active,both)
        if p.get("OnSelect","").startswith("=Set(varS01EnvChoice, ThisItem.Value)"):
            p["OnSelect"]+='; Set(varS01ServerReset, true); Set(varS01ServerReset, false)'
    # A gallery outside the form cannot call Reset on a form child. Drive
    # the dropdown's Reset input instead, preserving the two attachments.
    n1["DataCardValue3"]["Properties"]["Reset"]="=varS01ServerReset"
    s1["Properties"]["OnVisible"] += ''';
Set(varS01SettingsReadOk, true);
IfError(Refresh('架空ログ転記先'), Set(varS01SettingsReadOk, false));
If(!varS01SettingsReadOk, Set(varS01FlowStatus, "環境・サーバーの登録を読み取れません。進捗一覧へ戻り、もう一度開いてください。"));
If(varS01SettingsReadOk && !IsBlank(varS01EnvChoice) && IsBlank(LookUp('架空ログ転記先', cr6cb_environment = varS01EnvChoice && BOTH)), Set(varS01EnvChoice, Blank()); Reset(envS01ValueBridge); Set(varS01ServerReset, true); Set(varS01ServerReset, false))'''.replace("BOTH",both)
    pair="Filter('架空ログ転記先', cr6cb_environment = envS01ValueBridge.Selected.Value && cr6cb_server = DataCardValue3.Selected.Value && "+both+")"
    for key in ("btnT001Save","btnS01StartFlow"):
        p=n1[key]["Properties"];original=p["OnSelect"][1:]
        p["OnSelect"]='''=Set(varS01SettingsReadOk, true);
IfError(Refresh('架空ログ転記先'), Set(varS01SettingsReadOk, false));
If(varS01SettingsReadOk && CountRows(PAIR) = 1,
ORIGINAL,
Set(varS01FlowStatus, "選択した環境・サーバーを使用できません。登録内容を読み直し、環境とサーバーを選び直してください。"))'''.replace("PAIR",pair).replace("ORIGINAL",original)
    s2=screens["Screen2.pa.yaml"]["Screens"]["Screen2"];n2=nodes(s2)
    new=control("btnS02Management","Button",{"AccessibleLabel":'"環境・サーバーを管理"',"Appearance":"'ButtonCanvas.Appearance'.Secondary","Height":42,"Text":'"環境・サーバーを管理"',"OnSelect":"Navigate(Screen5, ScreenTransition.None)","Width":"If(Parent.Width < 760, Parent.Width - 48, 240)","X":"If(Parent.Width < 760, 24, btnS02ArchiveToggle.X + btnS02ArchiveToggle.Width + 12)","Y":"If(Parent.Width < 760, 178, 82)"})
    s2["Children"].insert(3,new)
    for key in ("btnS02NewIntake","btnS02ArchiveToggle"):
        for prop in ("Width","X","Y"):
            if prop in n2[key]["Properties"]:n2[key]["Properties"][prop]=n2[key]["Properties"][prop].replace("< 640","< 760")
    p=n2["galS02Cases"]["Properties"];p["Y"]="=If(Parent.Width < 760, 226, 138)";p["Height"]="=Max(80, Parent.Height - Self.Y - 16)"
    # Variable rows give long raw names/reasons their full height, without padding every ordinary row.
    n2["galS02Cases"]["Variant"]="VariableHeight"
    n2["lblS02Identity"]["Properties"]["AutoHeight"]="=true"
    n2["lblS02MqSummary"]["Properties"]["AutoHeight"]="=true"
    q=n2["lblS02MqSummary"]["Properties"]["Text"]
    q=q.replace('"照合できません: " & Coalesce(ThisItem.停止理由, "処理状態を確認してください")','"照合できません"')
    n2["lblS02MqSummary"]["Properties"]["Text"]=q
    p=n2["btnS02OpenCase"]["Properties"]
    p["Y"]='=Max(If(Parent.TemplateWidth >= 900, 238, lblS02HumanChecks.Y + lblS02HumanChecks.Height + 8), If(!IsBlank(ThisItem.停止理由), lblS02Failure.Y + lblS02Failure.Height + 8, 0))'
    n2["btnS02Archive"]["Properties"]["Y"]="=If(Parent.TemplateWidth >= 900, btnS02OpenCase.Y, btnS02OpenCase.Y + btnS02OpenCase.Height + 8)"
    n3=nodes(screens["Screen3.pa.yaml"]["Screens"]["Screen3"])
    p=n3["clip01_lblCaseExcelCheck"]["Properties"]
    p["Text"]='=If(varEvidenceCase.処理状態 = "停止" || varEvidenceCase.処理状態 = "結果不明", "照合できません", '+p["Text"][1:]+')'
    # A stopped comparison cannot later finish by waiting. Keep the actual
    # stop reason and suppress the pre-review waiting hint in that state.
    for obj in n3.values():
        p=obj.get("Properties",{})
        if '処理と結果Excelの確認が終わると依頼できます。' in p.get("Text",""):
            p["Visible"]='=varEvidenceCase.処理状態 <> "停止" && varEvidenceCase.処理状態 <> "結果不明" && ('+p["Visible"][1:]+')'
    return screens

class Dumper(yaml.SafeDumper):pass
def string(dumper,data):return dumper.represent_scalar("tag:yaml.org,2002:str",data,style="|" if "\n" in data else None)
Dumper.add_representer(str,string)

def main():
    # Historical builders above supply layout scaffolding. Do not regenerate
    # production screens from the obsolete environment-parent baseline.
    from prepare_server_first_canvas import main as generate_current
    generate_current()

if __name__=="__main__":main()
