init python in renspri:
    
    from numbers import Number
    from xml.etree import ElementTree
    from os import path
    import store
    
    store.config.automatic_images_strip += 'spriter', 'Spriter' #Prevents spriter images from being unnecessarily loaded
    
    output = [] #for debugging purposes
    
    def _import_all():
        def h():
            #some helpful functions to compress later code
            def i(x, attr, default=0): return int(x.get(attr, default)) #get int from element
            def f(x, attr, default='nan'): return float(x.get(attr, default)) #get float from element
            def id(x): return i(x, "id") #get id of element
            def fs(tree, arg, key=id): return sorted(tree.iterfind(arg), key=key) #Find elements and sort
            def uid(tree, arg): #iterates over every first item with a unique id
                seen = set()
                for elem in tree.iterfind(arg):
                    id = elem.get("id")
                    if id not in seen:
                        seen.add(id)
                        yield elem
            def suid(tree, arg, key=id): return sorted(uid(tree, arg), key=key) #sorts uid
            def zo(x): return i(x, "z_index") #get z index of element
            def conv(): #conversion dict
                def a(x): return 'xoffset', float(x)
                def b(x): return 'yoffset', float(x)
                def c(x): return 'rotate', float(x)
                return {'x': a, 'y': b, 'angle': c}
            conv = conv()
            def tim(x): return i(x, "time") #get time
            def key(elem, images, used): #generator for keydict
                k = tim(elem)
                yield "time", k
                elem = elem[0]
                k = elem.get("folder")
                if k:
                    k = images[int(k)][i(elem, "file")]
                    used.add(k)
                    yield "image", k
                for k, v in elem.attrib.iteritems():
                    if k in conv: yield conv[k](v)
            h.__dict__ = locals() #expose inner functions to the outside
        h() #also makes it possible to pass the entire function group as a single argument
        
        def img(root, imelem): return store.Image(path.join(root, imelem.get("name")),
            anchor=(h.f(imelem, "pivot_x"), h.f(imelem, "pivot_y"))) #Create an image displayable from an element
        for file in renpy.list_files():
            if '.scml' in file and 'autosave' not in file and renpy.loadable(file):
                root = path.dirname(file)
                with renpy.file(file) as scml:
                    tree = ElementTree.parse(scml)
                images = tuple(tuple(img(root, im) for im in h.fs(fol, "file"))for fol in h.fs(tree, "folder"))
                for entity in tree.findall("entity"):
                    tag = entity.get("name") + " "
                    for animation in entity.findall("animation"):
                        renpy.image(tag + animation.get("name"), Animation(animation, images, h))
                
    class Animation(renpy.Displayable):
        def __init__(self, tree, images, h, *args, **kwargs):
            super(type(self), self).__init__(*args, anchor=(0.5, 0.5), **kwargs)
            if isinstance(tree, ElementTree.Element) and tree.tag == "animation":
                self._length = h.i(tree, "length")
                self._interval = h.i(tree, "interval")
                used_images = set() #only include images that actually get used in the animation
                bones = [] #can't be a tuple because the sequence is used as an argument while being built
                for ref in h.suid(tree, "./mainline/key/bone_ref"): #bones don't need a permanent reference here
                    bones.append(self._Animator(self, tree, ref, bones, images, used_images, h))
                self._animators = tuple(self._Animator(self, tree, ref, bones, images, used_images, h) 
                    for ref in h.suid(tree, "./mainline/key/object_ref", h.zo))
                self._images = tuple(used_images)
  
        class _Animator(object):
            def __init__(self, root, tree, ref, parents, images, used_images, h, *args, **kwargs):
                super(type(self), self).__init__(*args, **kwargs)
                if isinstance(tree, ElementTree.Element) and tree.tag == "animation":
                    self._root = root
                    p = ref.get("parent")
                    if p: self._parent = parents[int(p)]
                    timeline = tree.find("./timeline[@id='{}']".format(ref.get("timeline")))
                    self._name = timeline.get("name")
                    mainline = tree.find("mainline")
                    keys = tuple({k: v for k, v in h.key(key, images, used_images)} 
                        for key in sorted(timeline.iterfind("./key"), key=h.tim))
                    def callback(t, st, at):
                        return None
                    self._callback = callback
            
            def _transform(child=None): #Creates a new transform, nested in the transforms of its ancestors
                if hasattr(self, '_parent'):
                    return self._parent._transform(Transform(child, self._callback))
                else:
                    return Transform(child, self._callback)
                        
        def render(self, width, height, st, at):
            transforms = []
            ww, hh = 0, 0
            for animator in self._animators:
                transform = animator._transform()
                trender = renpy.render(transform, width, height, st, at)
                transforms.append((transform, trender))
                w, h = trender.get_size()
                if w > ww: ww = w
                if h > hh: hh = h
            render = renpy.Render(ww, hh)
            for transform, trender in transforms:
                render.place(transform, render=trender)
            return render
            
        def visit(self):
            return self._images
                        
    class SpriterObject(renpy.Displayable):
        """
        A Spriter Entity consists of several SpriterObjects, be it the root Entity,
        Bones, or Parts. All of these can have children postioned relative to their
        parents. Base class, do not instantiate.
        """        
        def __init__(self, children=[], **kwargs):
            super(SpriterObject, self).__init__(**kwargs)
            
            #All the direct children of this object, may be other Bones or Parts
            self._children = children
            
        def render(self, width, height, st, at):
            """Generic render, simply renders its children"""
            render = renpy.Render(width, height)
            for child in _children:
                render.place(child)
            return render
            
        def visit(self):
            return self._children
         
    class Timeline():
        """Container for keyframes for a single child"""
        def __init__(self, keys, object, anim_length):
            #The list of keys, gets sorted by time
            keys.sort(key=lambda x: x.time)
            self._keys = keys
            self._length = len(keys)
            self._anim_length = anim_length
            
            #A transform containing a Spriter Object as a child
            self._obj = object
            
            #The most recent keyframe
            self._prev = 0
            self._speed = 100
            
        def _transform_callback(self):
            def c(trans, st, at):
                time = st * 100 % self._anim_length
                #global output
                #output = str(time)
                prev = self._prev
                next = prev + 1
                if next >= self._length:
                    next = 0
                while next != 0 and time > self._keys[next].time or time < self._keys[prev].time:
                    prev = self._prev = next
                    next += 1
                    if next >= self._length:
                        next = 0
                prev = self._keys[prev]
                props = prev._props
                if prev.time != time:
                    next = self._keys[next]
                    ptime, ntime = prev.time, next.time
                    prev, next = prev._props, next._props
                    fraction = float(time - ptime) / float(ntime - ptime)
                    props = {}
                    for k, prop in prev.items():
                        if k in next:
                            if prop != next[k]:
                                if isinstance(prop, Number):
                                    prop += (next[k] - prop) * fraction
                        props[k] = prop
                for name, val in props.items():
                    if name == 'image':
                        trans.set_child(val)
                    else:
                        setattr(trans, name, val)
                return 0
            return c
        
        def _transform(self):
            return store.Transform(self._obj, self._transform_callback())
                            
    class Key():
        """
        Contains positioning and transformation data for every frame
        of a Spriter animation.
        """
        
        def __init__(self, time, properties):
            #The frame that this key applies to
            self.time = time
            
            #A dict of properties to iterate through
            self._props = properties
            
    class AAnimation():
        """All the animation data."""
        def __init__(self, length, mainline, timelines):
            #All the keys of the animation, in a list
            self._mainline = mainline
            
            self._timelines = timelines
            
            #Length in frames
            self._length = length
            
        def _render(self, width, height, st, at):
            """Renders child Bones or Parts"""
            transform = self._timelines[0]._transform()
            tr = renpy.render(transform, width, height, st, at)
            r = renpy.Render(*tr.get_size())
            r.place(transform, render=tr)
            return r
            
    class Entity(SpriterObject):
        """
        The root-level SpriterObject. 
        Determines the total size of the thing, as well as the framerate.
        """
        def __init__(self, animations=[], speed=100, **kwargs):
            super(Entity, self).__init__(**kwargs)
            
            #A dict of all animations
            self._animations = animations
            for name in 'idle', 'Idle', 'default', 'Default', 'normal', 'Normal':
                if name in animations:
                    self.animate(name)
                    break
            
            #Animation speed in frames per second, this is different from the refresh rate
            self._speed = speed
            
        def animate(self, name):
            """Starts an animation."""
            #set the animation's start time
            self._start = 0
            self._current_anim = self._animations[name]
            
        def render(self, width, height, st, at):
            return self._current_anim._render(width, height, st, at)
    
    _import_all()