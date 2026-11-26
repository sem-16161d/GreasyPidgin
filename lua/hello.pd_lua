local hello = pd.Class:new():register("hello")

function hello:initialize()
    self.inlets = 1
    self.outlets = 1
    return true
end

function hello:in_1_float(f)
    self:outlet(1, "float", {f * 2})
end