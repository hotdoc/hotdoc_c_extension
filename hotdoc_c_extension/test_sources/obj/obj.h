#pragma once

#include <glib-object.h>

G_BEGIN_DECLS

G_DECLARE_DERIVABLE_TYPE (ObjObj, obj_obj, OBJ, OBJ, GObject)

struct _ObjObjClass
{
  GObjectClass parent;

  gpointer _padding[10];
};

G_END_DECLS
