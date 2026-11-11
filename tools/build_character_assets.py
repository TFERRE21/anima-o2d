"""Build reusable stylized 3D cast assets with Blender 5.x.
Run: blender --background --python tools/build_character_assets.py
Creates .blend and .glb per character under assets/characters/<id>/.
"""
import bpy, math, json
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"assets"/"characters"; OUT.mkdir(parents=True,exist_ok=True)
def mat(n,c,r=.45,metal=0):
 m=bpy.data.materials.new(n);m.diffuse_color=c;m.use_nodes=True
 bs=m.node_tree.nodes.get("Principled BSDF");bs.inputs["Base Color"].default_value=c;bs.inputs["Roughness"].default_value=r;bs.inputs["Metallic"].default_value=metal
 return m
M={"skin":mat("Skin warm peach",(.93,.57,.39,1)),"skin2":mat("Skin soft warm",(1,.74,.57,1)),"hair":mat("Hair espresso",(.12,.045,.025,1)),"hair2":mat("Hair chestnut",(.31,.105,.045,1)),"pink":mat("Luna rose suit",(.88,.055,.38,1),.32),"pink2":mat("Luna blush trim",(1,.30,.65,1),.32),"blue":mat("Tomi and Pipo explorer blue",(.035,.19,.56,1),.32),"blue2":mat("Sky trim",(.18,.58,.92,1),.3),"gold":mat("Adventure gold",(1,.58,.08,1),.28,.4),"white":mat("Eye ivory",(1,.97,.88,1),.2),"black":mat("Pupils",(.018,.012,.02,1),.2),"mouth":mat("Mouth",(.20,.035,.045,1)),"dog":mat("Pipo caramel coat",(.62,.29,.11,1)),"dog2":mat("Pipo cream muzzle",(.96,.72,.49,1)),"dogdark":mat("Pipo dark ears",(.34,.15,.075,1)),"metal":mat("Pearl alloy",(.42,.62,.72,1),.28,.5),"lens":mat("Aqua communicator",(.05,.78,.92,1),.2,.2)}
def finish(o,m):
 o.data.materials.append(m)
 if o.type=="MESH":
  for p in o.data.polygons:p.use_smooth=True
 return o
def uv(n,loc,scale,m):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=20,location=loc);o=bpy.context.object;o.name=n;o.scale=scale;return finish(o,m)
def cube(n,loc,scale,m):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=n;o.dimensions=scale;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);mod=o.modifiers.new("Soft edges","BEVEL");mod.width=.07;mod.segments=3;return finish(o,m)
def torus(n,loc,major,minor,m):
 bpy.ops.mesh.primitive_torus_add(major_radius=major,minor_radius=minor,major_segments=40,minor_segments=12,location=loc,rotation=(math.pi/2,0,0));o=bpy.context.object;o.name=n;return finish(o,m)
def addbone(arm,n,h,t,parent=None):
 b=arm.data.edit_bones.new(n);b.head=h;b.tail=t
 if parent:b.parent=arm.data.edit_bones[parent]
def rig(name,dog=False):
 d=bpy.data.armatures.new(name+" Rig");a=bpy.data.objects.new(name+" Controls",d);bpy.context.collection.objects.link(a);bpy.context.view_layer.objects.active=a;a.select_set(True);bpy.ops.object.mode_set(mode="EDIT")
 if dog:
  addbone(a,"root",(0,0,0),(0,0,.35));addbone(a,"spine",(0,0,.35),(0,0,1.05),"root");addbone(a,"neck",(0,-.25,1),(0,-.5,1.4),"spine");addbone(a,"head",(0,-.5,1.4),(0,-.7,1.9),"neck");addbone(a,"jaw",(0,-.68,1.55),(0,-.9,1.55),"head")
  for s,x in (("L",-.28),("R",.28)):
   addbone(a,"ear."+s,(x,-.48,1.72),(x*1.5,-.5,1.35),"head");addbone(a,"front_leg."+s,(x,-.32,.8),(x,-.4,.18),"spine");addbone(a,"rear_leg."+s,(x,.48,.72),(x,.42,.16),"root")
  addbone(a,"tail",(0,.65,.95),(0,1.18,1.15),"root")
 else:
  addbone(a,"root",(0,0,0),(0,0,.4));addbone(a,"pelvis",(0,0,.65),(0,0,1),"root");addbone(a,"spine",(0,0,1),(0,0,1.8),"pelvis");addbone(a,"neck",(0,0,1.8),(0,0,2.05),"spine");addbone(a,"head",(0,0,2.05),(0,0,2.8),"neck");addbone(a,"jaw",(0,-.15,2.25),(0,-.35,2.25),"head")
  for s,x in (("L",-.23),("R",.23)):
   addbone(a,"arm."+s,(x*2,0,1.65),(x*3,0,1),"spine");addbone(a,"hand."+s,(x*3,0,1),(x*3,-.08,.82),"arm."+s);addbone(a,"leg."+s,(x,0,.75),(x,0,.25),"pelvis");addbone(a,"foot."+s,(x,0,.25),(x,-.25,.12),"leg."+s)
 bpy.ops.object.mode_set(mode="OBJECT");a.show_in_front=True;a.data.display_type="OCTAHEDRAL";a["character_id"]=name.lower()+"-v1";return a
def attach(o,a,b):
 w=o.matrix_world.copy();o.parent=a;o.parent_type="BONE";o.parent_bone=b;o.matrix_world=w
def human(name,luna):
 a=rig(name);skin=M["skin"] if luna else M["skin2"];hair=M["hair"] if luna else M["hair2"];suit=M["pink"] if luna else M["blue"];trim=M["pink2"] if luna else M["blue2"]
 uv(name+" torso",(0,0,1.35),(.48,.32,.65),suit);uv(name+" chest panel",(0,-.285,1.48),(.34,.075,.38),trim);cube(name+" utility belt",(0,-.015,.88),(.88,.63,.15),M["gold"]);cube(name+" explorer backpack",(0,.34,1.38),(.62,.30,.78),M["metal"]);cube(name+" backpack panel",(0,.50,1.4),(.42,.035,.52),suit)
 uv(name+" neck",(0,0,1.94),(.17,.17,.22),skin);uv(name+" head",(0,-.045,2.37),(.62,.50,.68),skin);uv(name+" hair cap",(0,.015,2.78),(.64,.51,.32),hair);uv(name+" hair side L",(-.53,.02,2.4),(.14,.34,.4),hair);uv(name+" hair side R",(.53,.02,2.4),(.14,.34,.4),hair)
 if luna:
  for i,x in enumerate((-.34,-.12,.12,.34)):uv(name+" fringe "+str(i),(x,-.405,2.68),(.17,.13,.19),hair)
  torus(name+" signature inventor headband",(0,-.33,2.70),.43,.055,trim);uv(name+" golden star",(.47,-.39,2.68),(.105,.055,.105),M["gold"]);uv(name+" aqua communicator",(-.51,-.12,2.48),(.09,.08,.12),M["lens"])
 else:
  for i,(x,z,t) in enumerate([(-.4,2.68,-.25),(-.2,2.83,-.12),(0,2.88,0),(.2,2.83,.12),(.4,2.68,.25)]):
   o=uv(name+" swept hair "+str(i),(x,-.015,z),(.19,.2,.3),hair);o.rotation_euler[1]=t
  uv(name+" blue communicator",(.52,-.13,2.48),(.1,.08,.12),trim)
 iris=M["lens"] if luna else M["hair2"]
 for s,x in (("L",-.22),("R",.22)):
  uv(name+" eye white "+s,(x,-.475,2.42),(.14,.055,.19),M["white"]);uv(name+" iris "+s,(x,-.526,2.42),(.078,.035,.12),iris);uv(name+" pupil "+s,(x,-.553,2.42),(.041,.025,.075),M["black"]);uv(name+" eye glint "+s,(x-.025,-.575,2.47),(.025,.018,.03),M["white"]);b=uv(name+" brow "+s,(x,-.475,2.68),(.15,.045,.04),hair);b.rotation_euler[1]=-.1 if s=="L" else .1
 uv(name+" nose",(0,-.54,2.29),(.06,.045,.055),skin);uv(name+" mouth",(0,-.51,2.12),(.105,.045,.065),M["mouth"])
 for s,x in (("L",-.62),("R",.62)):
  uv(name+" shoulder "+s,(x*.82,0,1.67),(.2,.22,.2),trim);attach(uv(name+" arm "+s,(x,-.005,1.34),(.15,.17,.36),suit),a,"arm."+s);attach(uv(name+" glove "+s,(x,-.045,1.02),(.15,.15,.15),skin),a,"hand."+s);attach(uv(name+" leg "+s,(x*.38,0,.52),(.18,.2,.34),suit),a,"leg."+s);attach(uv(name+" boot "+s,(x*.38,-.09,.19),(.22,.29,.16),trim),a,"foot."+s)
 uv(name+" chest badge",(0,-.37,1.35),(.105,.045,.11),M["gold"]);return a
def pipo():
 n="Pipo";a=rig(n,True);uv(n+" body",(0,.05,.94),(.47,.72,.42),M["dog"]);uv(n+" cream chest",(0,-.43,.92),(.33,.18,.30),M["dog2"]);uv(n+" blue rescue vest",(0,-.015,1.03),(.49,.59,.28),M["blue"]);cube(n+" gold collar",(0,-.48,1.3),(.65,.14,.15),M["gold"]);uv(n+" head",(0,-.57,1.52),(.52,.46,.50),M["dog"]);uv(n+" forehead patch",(0,-.91,1.72),(.19,.06,.14),M["dog2"])
 for s,x in (("L",-.45),("R",.45)):
  attach(uv(n+" floppy ear "+s,(x,-.5,1.48),(.2,.22,.39),M["dogdark"]),a,"ear."+s);uv(n+" eye "+s,(x*.48,-.97,1.62),(.105,.045,.14),M["white"]);uv(n+" pupil "+s,(x*.48,-1.01,1.62),(.05,.025,.085),M["black"])
 uv(n+" muzzle L",(-.13,-.93,1.34),(.2,.16,.15),M["dog2"]);uv(n+" muzzle R",(.13,-.93,1.34),(.2,.16,.15),M["dog2"]);uv(n+" nose",(0,-1.075,1.39),(.11,.055,.075),M["black"]);uv(n+" mouth",(0,-1.01,1.2),(.1,.04,.06),M["mouth"]);uv(n+" tongue",(0,-1.04,1.15),(.055,.025,.055),M["pink2"])
 for s,x in (("L",-.26),("R",.26)):
  for prefix,y,z in (("front",-.38,.62),("rear",.48,.58)):attach(uv(n+" "+prefix+" leg "+s,(x,y,z),(.15,.18,.34),M["dog"]),a,prefix+"_leg."+s)
 attach(uv(n+" fluffy tail",(0,.85,1.03),(.15,.38,.15),M["dog"]),a,"tail");uv(n+" gold star badge",(0,-.57,1.05),(.12,.05,.12),M["gold"]);return a
def export(name,a):
 folder=OUT/name.lower();folder.mkdir(parents=True,exist_ok=True);bpy.ops.object.select_all(action="DESELECT")
 for o in bpy.context.scene.objects:
  if o==a or o.parent==a or o.name.startswith(name+" "):o.select_set(True)
 bpy.context.view_layer.objects.active=a;a["asset_version"]="1.0.0";a["character_name"]=name
 bpy.ops.wm.save_as_mainfile(filepath=str(folder/(name.lower()+".blend")))
 bpy.ops.export_scene.gltf(filepath=str(folder/(name.lower()+".glb")),export_format="GLB",use_selection=True,export_animations=True)
 bones=[b.name for b in a.data.bones];(folder/"manifest.json").write_text(json.dumps({"character":name,"version":"1.0.0","blend":name.lower()+".blend","glb":name.lower()+".glb","rig_object":a.name,"controls":bones},indent=2,ensure_ascii=False),encoding="utf-8")
 print("ANIMA_CHARACTER_ASSET_READY",name,flush=True)
def main():
 for name,builder in (("Luna",lambda:human("Luna",True)),("Tomi",lambda:human("Tomi",False)),("Pipo",pipo)):
  bpy.ops.object.select_all(action="SELECT");bpy.ops.object.delete(use_global=False);a=builder();export(name,a)
 print("ANIMA_CHARACTER_LIBRARY_COMPLETE",flush=True)
if __name__=="__main__":main()
