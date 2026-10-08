# Modifying Solver Behavior - Callbacks

int GRBcbsetintparam(void *cbdata, const char *paramname, int newvalue)

   Set an int-valued parameter from within a callback.

   Return value:
      Zero if successful.

   Parameters:
      * **cbdata** – The "cbdata" argument that was passed into the
        user callback.

      * **paramname** – The name of the parameter.

      * **newvalue** – The desired new value for the parameter.
